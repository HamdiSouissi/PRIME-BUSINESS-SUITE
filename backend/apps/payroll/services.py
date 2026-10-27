"""Services du cycle de paie : préparation, simulation, validation, édition.

Le cycle respecte les étapes du cahier des charges (section 5) :
préparation → contrôle des données → simulation → comparaison/anomalies →
validation (personne habilitée) → édition → mise à disposition → archivage.
"""

from datetime import date
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import BusinessError
from apps.core.models import Sequence

from .engine import compute_payslip, hash_result, q2
from .models import (
    ContributionRule,
    Payslip,
    PayslipLine,
    PayslipStatus,
    PayrollParameterSet,
    PayrollRun,
    RulesetStatus,
    RunStatus,
)


def ruleset_applicable(company, period_date: date):
    """Retourne le jeu de règles le plus récent couvrant la date donnée."""
    return (
        PayrollParameterSet.objects.filter(
            company=company,
            valid_from__lte=period_date,
            status__in=(RulesetStatus.PROVISOIRE, RulesetStatus.VERIFIE),
        )
        .filter(models_q_date(period_date))
        .order_by("-valid_from")
        .first()
    )


def models_q_date(period_date):
    from django.db.models import Q

    return Q(valid_to__isnull=True) | Q(valid_to__gte=period_date)


def _default_inputs(employee, contract, params) -> dict:
    heures_hebdo = Decimal(contract.weekly_hours or 35)
    heures_mensuelles = q2(heures_hebdo * Decimal("52") / 12)
    return {
        "salaire_base": str(contract.gross_monthly_salary),
        "primes": [],
        "retenues": [],
        "heures_sup": [],
        "avantages_nature": [],
        "remboursements": [],
        "taux_pas": str(contract.withholding_rate or 0),
        "is_cadre": bool(contract.is_cadre),
        "heures_mensuelles": str(heures_mensuelles),
    }


def verifier_donnees_cycle(run: PayrollRun) -> list[str]:
    """Contrôle des données manquantes avant simulation (étape 2)."""
    from apps.hr.models import ContractStatus, Employee

    anomalies = []
    if not Employee.objects.filter(company=run.company, status="actif").exists():
        anomalies.append("Aucun salarié actif dans l'entreprise.")
    employes = (
        Employee.objects.filter(company=run.company, status="actif")
        .prefetch_related("contrats")
    )
    for employee in employes:
        contrat = employee.contrat_actif
        if contrat is None:
            anomalies.append(f"{employee.full_name} : aucun contrat actif.")
            continue
        if not employee.social_security_number:
            anomalies.append(f"{employee.full_name} : numéro de sécurité sociale manquant.")
        if not employee.bank_iban:
            anomalies.append(f"{employee.full_name} : IBAN manquant (virement impossible).")
    return anomalies


@transaction.atomic
def generer_simulation(run: PayrollRun, user) -> list[Payslip]:
    """Étape 3 : (re)génère les bulletins simulés pour tous les salariés actifs."""
    if run.status == RunStatus.CLOTURE:
        raise BusinessError("Un cycle clôturé ne peut pas être modifié.", code="cycle_cloture")
    period_date = date(run.year, run.month, 1)
    params = ruleset_applicable(run.company, period_date)
    if params is None:
        raise BusinessError(
            "Aucun jeu de règles applicable à cette période. Créez des paramètres "
            "de paie couvrant la période.",
            code="pas_de_regles",
        )
    rules = list(params.rules.all())
    if not rules:
        raise BusinessError(
            "Le jeu de règles ne contient aucune cotisation.", code="regles_vides"
        )

    bulletins = []
    from apps.hr.models import ContractStatus, Employee

    employes = Employee.objects.filter(company=run.company, status="actif").prefetch_related("contrats")
    for employee in employes:
        contrat = employee.contrat_actif
        if contrat is None:
            continue
        payslip, created = Payslip.objects.select_for_update().get_or_create(
            company=run.company,
            run=run,
            employee=employee,
            defaults={
                "contract": contrat,
                "parameter_set": params,
                "inputs": _default_inputs(employee, contrat, params),
            },
        )
        if not created and payslip.status in {PayslipStatus.VALIDE, PayslipStatus.EDITE, PayslipStatus.CLOTURE}:
            continue  # un bulletin définitif n'est jamais recalculé silencieusement
        payslip.contract = contrat
        payslip.parameter_set = params
        result = compute_payslip(payslip.inputs, params, rules)
        payslip.result = result
        payslip.result_hash = hash_result(result)
        totaux = result["totaux"]
        payslip.brut = totaux["brut"]
        payslip.total_cotisations_salariales = totaux["total_cotisations_salariales"]
        payslip.total_cotisations_patronales = totaux["total_cotisations_patronales"]
        payslip.allegements = totaux["allegements"]
        payslip.net_social = totaux["net_social"]
        payslip.net_imposable = totaux["net_imposable"]
        payslip.prelevement_a_la_source = totaux["prelevement_a_la_source"]
        payslip.net_a_payer = totaux["net_a_payer"]
        payslip.cout_employeur = totaux["cout_employeur"]
        payslip.provisional = params.status != RulesetStatus.VERIFIE
        payslip.status = PayslipStatus.SIMULE
        payslip.save()
        # Réécrit les lignes calculées
        payslip.lines.all().delete()
        PayslipLine.objects.bulk_create(
            [
                PayslipLine(
                    payslip=payslip,
                    section=l["section"],
                    code=l["code"],
                    label=l["label"],
                    base=l["base"],
                    rate_salarial=l["rate_salarial"],
                    amount_salarial=l["amount_salarial"],
                    rate_patronal=l["rate_patronal"],
                    amount_patronal=l["amount_patronal"],
                    is_allegement=l["is_allegement"],
                    order=idx,
                )
                for idx, l in enumerate(result["cotisations"])
            ]
        )
        bulletins.append(payslip)

    run.status = RunStatus.SIMULATION
    run.log_step(user, f"Simulation générée pour {len(bulletins)} salariés.")
    run.save()
    return bulletins


def anomalies_vs_precedent(run: PayrollRun) -> list[str]:
    """Étape 4/5 : comparaison avec le cycle précédent (variation > seuil)."""
    anomalies = []
    previous = (
        PayrollRun.objects.filter(company=run.company)
        .filter(year__lt=run.year, )
        .exclude(pk=run.pk)
        .order_by("-year", "-month")
        .first()
    )
    if previous is None:
        return ["Aucun cycle précédent : première paie de l'historique."]
    seuil = Decimal("20")  # variation % signalée
    for bulletin in run.payslips.all():
        ancien = previous.payslips.filter(employee=bulletin.employee).first()
        if ancien is None:
            anomalies.append(f"{bulletin.employee.full_name} : nouveau salarié dans la paie.")
            continue
        if ancien.net_a_payer and ancien.net_a_payer > 0:
            variation = abs(bulletin.net_a_payer - ancien.net_a_payer) / ancien.net_a_payer * 100
            if variation > seuil:
                anomalies.append(
                    f"{bulletin.employee.full_name} : net à payer variant de {variation:.1f} % "
                    f"({ancien.net_a_payer} € → {bulletin.net_a_payer} €)."
                )
    return anomalies


@transaction.atomic
def valider_cycle(run: PayrollRun, user):
    """Étape 6 : validation par une personne habilitée.

    Bloquée si les règles utilisées ne sont pas vérifiées (conformité 5 bis).
    """
    if run.status not in {RunStatus.SIMULATION, RunStatus.CONTROLE, RunStatus.ATTENTE_VALIDATION}:
        raise BusinessError(
            "Le cycle doit être simulé et contrôlé avant validation.",
            code="transition_interdite",
        )
    bulletins = list(run.payslips.all())
    if not bulletins:
        raise BusinessError("Aucun bulletin simulé.", code="cycle_vide")
    if any(b.provisional for b in bulletins):
        raise BusinessError(
            "Validation définitive refusée : les règles de paie utilisées sont "
            "PROVISOIRES (non vérifiées par un expert). Faites vérifier le jeu de "
            "paramètres avant d'émettre une paie définitive.",
            code="regles_provisoires",
        )
    for bulletin in bulletins:
        if not bulletin.number:
            bulletin.number = Sequence.allocate(
                run.company, key="payslip", prefix="BS", year=run.year, padding=5
            )
        bulletin.status = PayslipStatus.VALIDE
        bulletin.save(update_fields=["status", "number", "updated_at"])
    run.status = RunStatus.VALIDE
    run.validated_by = user
    run.validated_at = timezone.now()
    run.log_step(user, "Cycle validé : bulletins définitifs émis.")
    run.save()
    return run


@transaction.atomic
def cloturer_cycle(run: PayrollRun, user):
    """Clôture : le cycle devient définitif, non modifiable, archivé."""
    if run.status != RunStatus.VALIDE:
        raise BusinessError("Seul un cycle validé peut être clôturé.", code="transition_interdite")
    for bulletin in run.payslips.all():
        bulletin.status = PayslipStatus.CLOTURE
        bulletin.save(update_fields=["status", "updated_at"])
    run.status = RunStatus.CLOTURE
    run.closed_at = timezone.now()
    run.log_step(user, "Cycle clôturé et archivé.")
    run.save()
    return run


def bulletin_html(payslip: Payslip) -> str:
    """HTML du bulletin, rendu depuis le gabarit avec données d'instantané."""
    from django.template.loader import render_to_string

    return render_to_string(
        "payroll/bulletin.html",
        {
            "bulletin": payslip,
            "company": payslip.company,
            "lines": payslip.lines.all(),
            "result": payslip.result,
        },
    )


@transaction.atomic
def editer_bulletin(payslip: Payslip, user=None):
    """Étape 7/8 : génère le PDF du bulletin validé et le met à disposition."""
    if payslip.status not in {PayslipStatus.VALIDE, PayslipStatus.EDITE, PayslipStatus.CLOTURE}:
        raise BusinessError(
            "Seul un bulletin validé peut être édité.", code="transition_interdite"
        )
    if hash_result(payslip.result) != payslip.result_hash:
        raise BusinessError(
            "Intégrité compromise : le résultat stocké ne correspond pas à son empreinte.",
            code="integrite",
        )
    from apps.core.services_pdf import html_vers_pdf

    pdf_bytes = html_vers_pdf(bulletin_html(payslip))
    filename = f"bulletin_{payslip.number or payslip.id}.pdf"
    payslip.pdf.save(filename, ContentFile(pdf_bytes), save=False)
    payslip.status = PayslipStatus.EDITE
    payslip.published_to_employee = True
    payslip.published_at = timezone.now()
    payslip.save(
        update_fields=["pdf", "status", "published_to_employee", "published_at", "updated_at"]
    )
    return payslip


# ---------------------------------------------------------------------------
# Jeu de règles de référence (France, 2025) — PROVISOIRE par défaut
# ---------------------------------------------------------------------------

def creer_ruleset_reference(company, user=None):
    """Crée le jeu de paramètres « France 2025 » avec ses cotisations.

    Source : valeurs publiées (URSSAF, BOSS) — le jeu est créé en statut
    PROVISOIRE : un expert doit le vérifier (action dédiée) pour autoriser
    la validation définitive des cycles de paie.
    """
    params = PayrollParameterSet.objects.create(
        company=company,
        label="Paramètres sociaux 2025 (référence)",
        status=RulesetStatus.PROVISOIRE,
        valid_from=date(2025, 1, 1),
        valid_to=None,
        source_url="https://www.urssaf.fr",
        source_label=(
            "SMIC 11,88 € (nov. 2024) ; PMSS 2025 : 3 925 € ; PASS 2025 : 47 100 €. "
            "Taux indicatifs à vérifier selon la convention collective et l'effectif."
        ),
        verification_note="Jeu de référence — vérification experte obligatoire avant usage réel.",
    )
    regles = [
        # code, label, section, base, plafond(xPMSS), tx sal, tx pat, cadre, non-cadre, ndCSG, patTaxable, ordre
        ("MALADIE", "Assurance maladie, maternité, invalidité, décès", "sante", "brut", 0, "0", "13.00", False, False, False, False, 10),
        ("ATMP", "Accidents du travail / maladies professionnelles", "at_mp", "brut", 0, "0", "0.50", False, False, False, False, 20),
        ("VIEIL-PLAF", "Vieillesse plafonnée", "retraite", "tranche_a", 1, "6.90", "8.55", False, False, False, False, 30),
        ("VIEIL-DEPLAF", "Vieillesse déplafonnée", "retraite", "brut", 0, "0.40", "2.02", False, False, False, False, 40),
        ("CHOMAGE", "Assurance chômage", "chomage", "brut", 4, "0", "4.05", False, False, False, False, 50),
        ("AGIRC-T1", "Retraite complémentaire AGIRC-ARRCO T1", "retraite", "tranche_a", 1, "3.15", "4.72", False, False, False, False, 60),
        ("AGIRC-T2", "Retraite complémentaire AGIRC-ARRCO T2 (cadres)", "retraite", "tranche_b", 1, "8.64", "12.95", True, False, False, False, 61),
        ("CEG-T1", "CEG tranche 1", "retraite", "tranche_a", 1, "0.86", "1.29", False, False, False, False, 62),
        ("CEG-T2", "CEG tranche 2 (cadres)", "retraite", "tranche_b", 1, "1.08", "1.62", True, False, False, False, 63),
        ("CET", "CET", "retraite", "brut", 8, "0.14", "0.21", False, False, False, False, 64),
        ("APEC", "APEC (cadres)", "autres", "brut", 4, "0.024", "0.036", True, False, False, False, 65),
        ("PREV-NC", "Prévoyance non-cadres", "prevoyance", "tranche_a", 1, "0", "1.00", False, True, False, True, 66),
        ("PREV-CAD", "Prévoyance cadres (min. 1,50 % TA)", "prevoyance", "tranche_a", 1, "0", "1.50", True, False, False, True, 67),
        ("FAMILLE", "Allocations familiales (taux réduit)", "famille", "brut", 0, "0", "3.45", False, False, False, False, 70),
        ("FNAL", "FNAL (< 50 salariés)", "autres", "brut", 0, "0", "0.10", False, False, False, False, 71),
        ("CSA", "Contribution solidarité autonomie", "autres", "brut", 0, "0", "0.30", False, False, False, False, 72),
        ("FORMA-PRO", "Formation professionnelle (< 50 salariés)", "autres", "brut", 0, "0", "1.00", False, False, False, False, 73),
        ("TAXE-APPR", "Taxe d'apprentissage", "autres", "brut", 0, "0", "0.68", False, False, False, False, 74),
        ("CSG-DED", "CSG déductible", "csg_crds", "csg_base", 4, "6.80", "0", False, False, False, False, 80),
        ("CSG-ND", "CSG non déductible", "csg_crds", "csg_base", 4, "2.40", "0", False, False, True, False, 81),
        ("CRDS", "CRDS non déductible", "csg_crds", "csg_base", 4, "0.50", "0", False, False, True, False, 82),
    ]
    ContributionRule.objects.bulk_create(
        [
            ContributionRule(
                parameter_set=params,
                code=code,
                label=label,
                section=section,
                base_type=base,
                ceiling_multiple=plafond,
                rate_salarial=tx_sal,
                rate_patronal=tx_pat,
                cadre_only=cadre,
                non_cadre_only=non_cadre,
                affects_net_imposable=nd_csg,
                patronal_part_taxable=pat_tax,
                order=ordre,
            )
            for (code, label, section, base, plafond, tx_sal, tx_pat, cadre, non_cadre, nd_csg, pat_tax, ordre) in regles
        ]
    )
    return params
