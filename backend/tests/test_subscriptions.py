"""Abonnements : génération idempotente des factures et indicateurs MRR/ARR."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.invoicing.models import Client, Invoice
from apps.subscriptions.models import Periodicity, Subscription, SubscriptionInvoice, SubscriptionStatus
from apps.subscriptions import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def abonnement(company):
    client = Client.objects.create(company=company, code="C01", name="Client Un")
    return Subscription.objects.create(
        company=company, client=client, label="Maintenance Pro",
        periodicity=Periodicity.MENSUEL, price_ht=Decimal("500"),
        vat_rate=Decimal("20"),
        start_date=date(2025, 1, 1),
        next_billing_date=date.today() - timedelta(days=1),
    )


def test_generation_facture_et_avancement(abonnement):
    link = services.generer_facture_echeance(abonnement)
    assert link is not None
    abonnement.refresh_from_db()
    assert link.invoice.status == "emise"
    assert link.invoice.number.startswith("FA")
    assert abonnement.next_billing_date > link.period_start


def test_idempotence_relances_techniques(abonnement):
    """Exécuter deux fois la même journée ne produit qu'une seule facture."""
    n1 = services.generer_factures_echues_company(abonnement.company)
    n2 = services.generer_factures_echues_company(abonnement.company)
    assert n2 == 0
    factures = Invoice.objects.filter(source=f"abonnement:{abonnement.id}")
    assert factures.count() == n1
    # Unicité base de données : une échéance = une facture
    assert SubscriptionInvoice.objects.filter(subscription=abonnement).count() == n1


def test_contrainte_unicite_periode(abonnement):
    """Impossible de créer deux liens de facturation pour la même période."""
    link = services.generer_facture_echeance(abonnement)
    with pytest.raises(Exception):
        SubscriptionInvoice.objects.create(
            company=abonnement.company, subscription=abonnement,
            invoice=link.invoice, period_start=link.period_start,
            period_end=link.period_end,
        )


def test_indicateurs_mrr_arr(company):
    client = Client.objects.create(company=company, code="MRR", name="Client MRR")
    Subscription.objects.create(
        company=company, client=client, label="A", periodicity="mensuel",
        price_ht=Decimal("100"), start_date=date(2025, 1, 1),
        next_billing_date=date(2026, 3, 1), status="actif",
    )
    Subscription.objects.create(
        company=company, client=client, label="B", periodicity="annuel",
        price_ht=Decimal("1200"), start_date=date(2025, 1, 1),
        next_billing_date=date(2026, 3, 1), status="actif",
    )
    inds = services.indicateurs(company)
    assert inds["mrr_ht"] == Decimal("200.00")  # 100 + 1200/12
    assert inds["arr_ht"] == Decimal("2400.00")
    assert inds["abonnements_actifs"] == 2


def test_suspendu_non_facture(abonnement):
    abonnement.status = SubscriptionStatus.SUSPENDU
    abonnement.save()
    assert services.generer_facture_echeance(abonnement) is None
