"""Paie : moteur de règles versionnées, cas de référence, cycle et intégrité.

Ces tests valident le FONCTIONNEMENT TECHNIQUE du moteur. La CONFORMITÉ
RÉGLEMENTAIRE des taux (jauge par un spécialiste de la paie) est hors de la
portée des tests automatisés — voir docs/limites-reglementaires.md.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.core.exceptions import BusinessError
from apps.payroll.engine import compute_payslip, hash_result
from apps.payroll.models import (
    PayrollParameterSet,
    PayrollRun,
    Payslip,
    PayslipStatus,
    RulesetStatus,
    RunStatus,
)
from apps.payroll import services

pytestmark = pytest.mark.django_db


def _inputs(brut="2500", pas="0", cadre=False, **extra):
    base = {
        "salaire_base": brut,
        "primes": [],
        "retenues": [],
        "heures_sup": [],
        "avantages_nature": [],
        "remboursements": [],
        "taux_pas": pas,
        "is_cadre": cadre,
        "heures_mensuelles": "151.67",
    }
    base.update(extra)
    return base


def test_moteur_deterministe(ruleset):
    """Mêmes entrées + même jeu de règles = même résultat à l'octet près."""
    regles = list(ruleset.rules.all())
    a = compute_payslip(_inputs(), ruleset, regles)
    b = compute_payslip(_inputs(), ruleset, regles)
    assert hash_result(a) == hash_result(b)


def test_invariants_comptables_bulletin(ruleset):
    """Invariant structurel : brut − cotisations sal = net social, etc."""
    regles = list(ruleset.rules.all())
    r = compute_payslip(_inputs("2500", pas="5"), ruleset, regles)
    t = {k: Decimal(v) for k, v in r["totaux"].items()}
    assert t["brut"] == Decimal("2500.00")
    assert t["net_social"] == t["brut"] - t["total_cotisations_salariales"]
    assert t["net_a_payer"] == t["net_a_payer_avant_impot"] - t["prelevement_a_la_source"]
    assert t["cout_employeur"] == t["brut"] + t["total_cotisations_patronales"]
    assert t["total_cotisations_salariales"] > 0
    assert t["total_cotisations_patronales"] > 0
    # Taux global de cotisations salariales plausible (< 30 % du brut)
    assert t["total_cotisations_salariales"] / t["brut"] < Decimal("0.30")


def test_cas_reference_non_cadre_2500(ruleset):
    """Cas de référence : salarié non cadre 35 h à 2 500 € brut.

    Attendus RECALCULÉS à la main depuis les règles du jeu (script de contrôle
    docs/payroll/cas-reference-2500.md). Toute modification non voulue des règles
    fait échouer ce test de non-régression.
    """
    r = compute_payslip(_inputs("2500"), ruleset, list(ruleset.rules.all()))
    t = {k: Decimal(v) for k, v in r["totaux"].items()}
    # CSG base = 2500 × 98,25 % = 2456,25
    assert t["assiette_csg"] == Decimal("2456.25")
    # Vieillesse plafonnée salariale = min(2500, 3925) × 6,90 % = 172,50
    assert any(
        l["code"] == "VIEIL-PLAF" and Decimal(l["amount_salarial"]) == Decimal("172.50")
        for l in r["cotisations"]
    )
    # Réduction générale active sous 1,6 SMIC
    assert r["reduction_generale"] is not None
    assert t["net_social"] < t["brut"]


def test_cadre_tranche_b(ruleset):
    """Un cadre à 6 500 € cotise sur les tranches A et B (PMSS 3925)."""
    r = compute_payslip(_inputs("6500", cadre=True), ruleset, list(ruleset.rules.all()))
    ta = Decimal(r["totaux"]["tranche_a"])
    tb = Decimal(r["totaux"]["tranche_b"])
    assert ta == Decimal("3925.00")
    assert tb == Decimal("2575.00")
    codes = {l["code"] for l in r["cotisations"]}
    assert "AGIRC-T2" in codes and "APEC" in codes
    # Au-delà de 1,6 SMIC : pas d'allègement
    assert r["reduction_generale"] is None  # brut 6500 > 1.6 × 1801.80


def test_heures_supplementaires(ruleset):
    r = compute_payslip(
        _inputs("2500", heures_sup=[{"hours": "4", "majoration": "25"}]),
        ruleset, list(ruleset.rules.all()),
    )
    hs = [l for l in r["lignes_brut"] if "Heures supplémentaires" in l["label"]]
    assert hs, "ligne HS absente"
    # taux horaire = 2500/151.67 ≈ 16,48 ; 4 h × 1,25 → ≈ 82,42
    assert Decimal("80") < Decimal(hs[0]["amount"]) < Decimal("85")
    assert Decimal(r["totaux"]["brut"]) > Decimal("2500")


def test_cycle_validation_bloquee_si_provisoire(company, employee, paie_user, ruleset):
    run = PayrollRun.objects.create(company=company, year=2026, month=3, started_by=paie_user)
    services.generer_simulation(run, paie_user)
    assert run.payslips.count() == 1
    with pytest.raises(BusinessError) as exc:
        services.valider_cycle(run, paie_user)
    assert exc.value.code == "regles_provisoires"


def test_cycle_complet_apres_verification(company, employee, paie_user, ruleset_verifie):
    run = PayrollRun.objects.create(company=company, year=2026, month=3, started_by=paie_user)
    services.generer_simulation(run, paie_user)
    services.valider_cycle(run, paie_user)
    bulletin = run.payslips.first()
    assert bulletin.number.startswith("BS2026-")
    assert bulletin.status == PayslipStatus.VALIDE
    services.editer_bulletin(bulletin, paie_user)
    assert bulletin.pdf, "Le PDF doit être généré"
    assert bulletin.published_to_employee is True
    services.cloturer_cycle(run, paie_user)
    # Cycle clôturé : toute modification est rejetée
    with pytest.raises(BusinessError):
        services.generer_simulation(run, paie_user)


def test_integrite_hash_bulletin(company, employee, paie_user, ruleset_verifie):
    run = PayrollRun.objects.create(company=company, year=2026, month=4, started_by=paie_user)
    services.generer_simulation(run, paie_user)
    services.valider_cycle(run, paie_user)
    bulletin = run.payslips.first()
    bulletin.refresh_from_db()
    # Falsification silencieuse du résultat → l'édition doit se refuser
    bulletin.result["totaux"]["net_a_payer"] = "999999.99"
    bulletin.save(update_fields=["result"])
    with pytest.raises(BusinessError) as exc:
        services.editer_bulletin(bulletin, paie_user)
    assert exc.value.code == "integrite"


def test_unicite_bulletin_par_cycle(company, employee, paie_user, ruleset):
    run = PayrollRun.objects.create(company=company, year=2026, month=5, started_by=paie_user)
    Payslip.objects.create(
        company=company, run=run, employee=employee,
        parameter_set=ruleset,
    )
    with pytest.raises(Exception):
        Payslip.objects.create(company=company, run=run, employee=employee, parameter_set=ruleset)


def test_rules_versionnes_gel_apres_usage(company, employee, paie_user, ruleset, api_client):
    run = PayrollRun.objects.create(company=company, year=2026, month=6, started_by=paie_user)
    services.generer_simulation(run, paie_user)
    # Le jeu de règles a servi : PATCH d'une règle → refusé (gel)
    rule = ruleset.rules.first()
    api_client.force_authenticate(paie_user)
    r = api_client.patch(f"/api/payroll/rules/{rule.id}/", {"rate_salarial": "99"}, format="json")
    assert r.status_code == 400
    assert r.json()["code"] == "regles_gelees"
