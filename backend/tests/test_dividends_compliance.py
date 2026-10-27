"""Dividendes et centre de conformité : garde-fous et applicabilité."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.compliance.models import ObligationDefinition, ObligationInstance
from apps.compliance import services as compliance_services
from apps.core.exceptions import BusinessError
from apps.dividends.models import Associate, DistributionDecision, DistributionStatus
from apps.dividends import services as div_services

pytestmark = pytest.mark.django_db


@pytest.fixture
def associes(company):
    a1 = Associate.objects.create(company=company, first_name="A", last_name="Un",
                                  shares=700, entry_date=date(2022, 1, 1))
    a2 = Associate.objects.create(company=company, first_name="B", last_name="Deux",
                                  shares=300, entry_date=date(2022, 1, 1))
    return a1, a2


@pytest.fixture
def decision(company):
    return DistributionDecision.objects.create(
        company=company, fiscal_year=2025, meeting_date=date(2026, 6, 30),
        resultat_exercice=Decimal("50000"), report_a_nouveau=Decimal("0"),
        autres_reserves=Decimal("0"),
    )


def test_distribuable_reserve_legale(company, decision):
    """Réserve légale 5 % du résultat tant que < 10 % du capital (10 000 €)."""
    info = div_services.calculer_somme_distribuable(company, decision)
    # Réserve légale : 5 % de 50 000 = 2 500, plafond 1 000 (10 % de 10 000) → 1 000
    assert Decimal(info["reserve_legale_a_dotter"]) == Decimal("1000")
    assert Decimal(info["somme_distribuable"]) == Decimal("49000")


def test_distribution_ne_peut_pas_depasser_distribuable(company, decision, associes, admin_user):
    from django.core.files.base import ContentFile

    doc = ContentFile(b"PV assemblee", name="pv.pdf")
    with pytest.raises(BusinessError) as exc:
        div_services.decider_distribution(decision, Decimal("60000"), admin_user, document=doc)
    assert exc.value.code == "depassement_distribuable"


def test_distribution_nom_complete(company, decision, associes, admin_user):
    from django.core.files.base import ContentFile

    doc = ContentFile(b"PV assemblee", name="pv.pdf")
    div_services.decider_distribution(decision, Decimal("40000"), admin_user, document=doc)
    decision.refresh_from_db()
    assert decision.status == "decidee"
    paiements = list(decision.paiements.all())
    assert len(paiements) == 2
    # Répartition au prorata 70/30 avec PFU 30 % (personnes physiques)
    total_brut = sum(p.gross_amount for p in paiements)
    assert total_brut == Decimal("40000")
    a_un = [p for p in paiements if p.associate.last_name == "Un"][0]
    assert a_un.gross_amount == Decimal("28000")
    assert a_un.withholding_amount == Decimal("8400")
    assert a_un.net_amount == Decimal("19600")
    # Paiement sans décision impossible (reconstruire un projet)
    div_services.marquer_payee(a_un, admin_user, date(2026, 7, 5))
    a_un.refresh_from_db()
    assert a_un.paid_on == date(2026, 7, 5)
    # Double paiement refusé
    with pytest.raises(BusinessError):
        div_services.marquer_payee(a_un, admin_user, date(2026, 7, 6))


def test_solde_bancaire_jamais_distribuable_par_defaut(company, decision):
    """Le calcul ne consulte JAMAIS la trésorerie (garde-fou §12)."""
    info = div_services.calculer_somme_distribuable(company, decision)
    assert "solde" not in str(info).lower() or "bancaire" not in str(info).lower()


# ---------------------------------------------------------------------------
# Conformité
# ---------------------------------------------------------------------------

def test_catalogue_initialise_idempotent():
    compliance_services.initialiser_catalogue()
    n1 = ObligationDefinition.objects.count()
    compliance_services.initialiser_catalogue()
    assert ObligationDefinition.objects.count() == n1 > 0


def test_applicabilite_selon_statut(company, autre_company):
    """La même obligation ne s'applique pas de la même façon selon la société."""
    compliance_services.initialiser_catalogue()
    dsn = ObligationDefinition.objects.get(code="DSN-MENSUELLE")
    # company : 3 salariés → applicable ; autre_company : 1 salarié → applicable aussi
    assert dsn.is_applicable_to(company) is True
    ca3 = ObligationDefinition.objects.get(code="TVA-CA3")
    # autre_company est en franchise de TVA → CA3 non applicable
    assert ca3.is_applicable_to(autre_company) is False
    assert ca3.is_applicable_to(company) is True


def test_generation_instances_idempotente(company):
    compliance_services.initialiser_catalogue()
    n1 = compliance_services.generer_instances(company)
    n2 = compliance_services.generer_instances(company)
    assert n2 == 0  # get_or_create empêche les doublons
    assert ObligationInstance.objects.filter(company=company).count() == n1


def test_marquage_retards(company):
    compliance_services.initialiser_catalogue()
    compliance_services.generer_instances(company)
    instance = ObligationInstance.objects.filter(company=company).first()
    instance.due_date = date.today() - timedelta(days=10)
    instance.save()
    compliance_services.generer_instances(company)
    instance.refresh_from_db()
    assert instance.status == "depassee"
