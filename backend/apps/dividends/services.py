"""Règles de distribution : garde-fous légaux et calcul des paiements."""

from decimal import Decimal

from django.db import transaction

from apps.core.exceptions import BusinessError

from .models import Associate, DistributionDecision, DistributionStatus, DividendPayment

CENT = Decimal("0.01")


def q2(v) -> Decimal:
    return Decimal(v).quantize(CENT)


def calculer_somme_distribuable(company, decision: DistributionDecision) -> dict:
    """Calcule la somme distribuable selon les informations déclarées.

    Base : résultat de l'exercice + report à nouveau + réserves distribuables.
    Réserve légale : 5 % du résultat si bénéficiaire, jusqu'à 10 % du capital
    (règles applicables aux SARL/SAS/EURL/SASU ; l'expert-comptable valide).
    Le solde bancaire n'intervient JAMAIS dans ce calcul (§12).
    """
    resultat = decision.resultat_exercice
    capital = company.share_capital or Decimal(0)
    reserve_legale_requise = Decimal(0)
    limite = capital * Decimal("0.10")
    if resultat > 0 and capital > 0:
        existante = _reserve_legale_comptable(company)
        dotation = resultat * Decimal("0.05")
        if existante + dotation > limite:
            dotation = max(Decimal(0), limite - existante)
        reserve_legale_requise = q2(dotation)
    somme = q2(decision.resultat_exercice + decision.report_a_nouveau + decision.autres_reserves - reserve_legale_requise)
    return {
        "resultat": str(resultat),
        "report_a_nouveau": str(decision.report_a_nouveau),
        "reserves": str(decision.autres_reserves),
        "reserve_legale_a_dotter": str(reserve_legale_requise),
        "somme_distribuable": str(somme),
        "avertissement": (
            "Ce calcul est un outil d'aide ; la somme distribuable doit être "
            "arrêtée sur les comptes approuvés par l'expert-comptable."
        ),
    }


def _reserve_legale_comptable(company) -> Decimal:
    """Solde du compte de réserve légale (1061) si comptabilisé."""
    from apps.accounting.models import EntryLine, EntryStatus
    from django.db.models import Sum

    agg = EntryLine.objects.filter(
        entry__company=company,
        entry__status__in=(EntryStatus.VALIDEE, EntryStatus.CONTRE_PASSEE),
        account__number__startswith="1061",
    ).aggregate(c=Sum("credit"), d=Sum("debit"))
    return (agg["c"] or Decimal(0)) - (agg["d"] or Decimal(0))


@transaction.atomic
def decider_distribution(decision: DistributionDecision, montant: Decimal, user, document=None):
    """Décision en assemblée : montant ≤ somme distribuable + PV obligatoire."""
    if decision.status != DistributionStatus.PROJET:
        raise BusinessError("Cette distribution a déjà été décidée.", code="transition_interdite")
    info = calculer_somme_distribuable(decision.company, decision)
    somme = Decimal(info["somme_distribuable"])
    if montant <= 0:
        raise BusinessError("Le montant décidé doit être positif.", code="montant_invalide")
    if montant > somme:
        raise BusinessError(
            f"Montant décidé ({montant} €) supérieur à la somme distribuable ({somme} €).",
            code="depassement_distribuable",
        )
    if document is None and not decision.decision_document:
        raise BusinessError(
            "Le PV d'assemblée approuvant la distribution est obligatoire.",
            code="pv_requis",
        )
    if document is not None:
        decision.decision_document = document
    decision.somme_distribuable = somme
    decision.montant_decide = montant
    decision.status = DistributionStatus.DECIDEE
    decision.decided_by = user
    decision.save()
    # Prépare les paiements au prorata des parts
    associes = Associate.objects.filter(company=decision.company, exit_date__isnull=True)
    total_parts = sum(a.shares for a in associes) or 1
    taux_retenue = Decimal(str(decision.withholding_rate or 0))
    for associe in associes:
        brut = q2(montant * associe.shares / total_parts)
        retenue = q2(brut * taux_retenue / 100) if not associe.is_company else Decimal(0)
        DividendPayment.objects.get_or_create(
            company=decision.company,
            decision=decision,
            associate=associe,
            defaults={
                "gross_amount": brut,
                "withholding_amount": retenue,
                "net_amount": brut - retenue,
            },
        )
    return decision


@transaction.atomic
def marquer_payee(paiement: DividendPayment, user, date_paiement, preuve=None):
    if paiement.decision.status != DistributionStatus.DECIDEE:
        raise BusinessError(
            "Paiement impossible : décision d'assemblée non actée.", code="transition_interdite"
        )
    if paiement.paid_on:
        raise BusinessError("Paiement déjà enregistré.", code="deja_paye")
    paiement.paid_on = date_paiement
    paiement.paid_by = user
    if preuve is not None:
        paiement.proof = preuve
    paiement.save()
    return paiement
