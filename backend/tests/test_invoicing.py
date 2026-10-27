"""Facturation : numérotation, totaux, avoirs, paiements defensifs."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.exceptions import BusinessError
from apps.invoicing.models import Client, Invoice, InvoiceLine, InvoiceStatus, InvoiceType
from apps.invoicing import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def client_obj(company):
    return Client.objects.create(company=company, code="C01", name="Client Un",
                                 payment_terms_days=30)


def _invoice(company, client):
    return Invoice.objects.create(
        company=company, client=client, status=InvoiceStatus.BROUILLON,
        issue_date=date(2026, 2, 1), due_date=date(2026, 3, 3),
    )


LIGNES_2 = [
    {"description": "Prestation de développement", "quantity": "10", "unit_price_ht": "500", "vat_rate": "20"},
    {"description": "Licence annuelle", "quantity": "1", "unit_price_ht": "1200", "vat_rate": "20"},
]


def test_totaux_calcules_serveur(company, client_obj):
    invoice = _invoice(company, client_obj)
    services.remplacer_lignes_invoice(invoice, LIGNES_2)
    invoice.refresh_from_db()
    # 10×500 = 5000 HT, TVA 1000 ; 1200 HT, TVA 240
    assert invoice.total_ht == Decimal("6200.00")
    assert invoice.total_vat == Decimal("1240.00")
    assert invoice.total_ttc == Decimal("7440.00")


def test_numerotation_sequentielle_par_annee(company, client_obj):
    a = services.remplacer_lignes_invoice(_invoice(company, client_obj), LIGNES_2[:1])
    services.emettre_invoice(a)
    b = services.remplacer_lignes_invoice(_invoice(company, client_obj), LIGNES_2[:1])
    services.emettre_invoice(b)
    assert a.number == "FA2026-00001"
    assert b.number == "FA2026-00002"


def test_facture_emise_non_modifiable_ni_supprimable(company, client_obj, admin_user, api_client):
    invoice = services.remplacer_lignes_invoice(_invoice(company, client_obj), LIGNES_2[:1])
    services.emettre_invoice(invoice)
    api_client.force_authenticate(admin_user)
    r = api_client.patch(f"/api/invoicing/invoices/{invoice.id}/", {"notes": "test"}, format="json")
    assert r.status_code == 400
    r = api_client.delete(f"/api/invoicing/invoices/{invoice.id}/")
    assert r.status_code == 400  # suppression silencieuse interdite
    assert Invoice.objects.filter(pk=invoice.id).exists()


def test_avoir_annule_la_facture(company, client_obj):
    invoice = services.remplacer_lignes_invoice(_invoice(company, client_obj), LIGNES_2[:1])
    services.emettre_invoice(invoice)
    avoir = services.creer_avoir(invoice, motif="Erreur de montant")
    services.emettre_invoice(avoir)
    avoir.refresh_from_db()
    invoice.refresh_from_db()
    assert avoir.number.startswith("AV2026-")
    assert avoir.total_ttc == -invoice.total_ttc
    assert invoice.status == InvoiceStatus.ANNULEE
    # Un seul avoir par facture
    with pytest.raises(BusinessError):
        services.creer_avoir(invoice)


def test_paiements_partiels_puis_solde(company, client_obj):
    # Total TTC des 2 lignes : 6 200 HT + 1 240 TVA = 7 440
    invoice = services.remplacer_lignes_invoice(_invoice(company, client_obj), LIGNES_2)
    services.emettre_invoice(invoice)
    services.enregistrer_paiement(company, invoice=invoice, date=date(2026, 2, 10),
                                  amount=Decimal("3000"), method="virement")
    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.PARTIELLEMENT_PAYEE
    assert invoice.amount_paid == Decimal("3000")
    services.enregistrer_paiement(company, invoice=invoice, date=date(2026, 2, 20),
                                  amount=Decimal("4440"), method="virement")
    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.PAYEE
    assert invoice.reste_a_payer == 0


def test_relance_niveau_unique(company, client_obj, admin_user):
    invoice = services.remplacer_lignes_invoice(_invoice(company, client_obj), LIGNES_2[:1])
    services.emettre_invoice(invoice)
    services.relancer_facture(invoice, admin_user, level=1)
    with pytest.raises(BusinessError):
        services.relancer_facture(invoice, admin_user, level=1)


def test_facture_sans_lignes_non_emise(company, client_obj):
    invoice = _invoice(company, client_obj)
    with pytest.raises(BusinessError):
        services.emettre_invoice(invoice)
