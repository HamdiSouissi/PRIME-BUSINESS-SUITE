"""Trésorerie : import CSV sans doublons, rapprochement, prévisionnel."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.exceptions import BusinessError
from apps.invoicing.models import Client, Invoice, InvoiceStatus, Payment
from apps.treasury.models import BankAccount, BankTransaction
from apps.treasury import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def compte(company):
    return BankAccount.objects.create(
        company=company, label="Compte principal", bank_name="Banque",
        is_main=True, initial_balance=Decimal("1000"), initial_balance_date=date(2026, 1, 1),
    )


CSV = "Date;Libellé;Montant\n15/01/2026;Virement ACME;1200,50\n16/01/2026;Prélèvement EDF;-230,00\n"


def test_import_csv_et_dedoublonnage(compte):
    r1 = services.importer_csv(compte, CSV.encode())
    assert r1["importees"] == 2
    r2 = services.importer_csv(compte, CSV.encode())
    assert r2["importees"] == 0
    assert r2["doublons_ignores"] == 2
    assert BankTransaction.objects.count() == 2


def test_solde_bancaire(compte):
    services.importer_csv(compte, CSV.encode())
    assert services.solde_bancaire(compte) == Decimal("1970.50")


def test_rapprochement_coherent(company, compte, comptable_user):
    client = Client.objects.create(company=company, code="C1", name="Client")
    invoice = Invoice.objects.create(
        company=company, client=client, status=InvoiceStatus.EMISE,
        issue_date=date(2026, 1, 5), due_date=date(2026, 2, 5),
        total_ht=Decimal("1000"), total_vat=Decimal("200"), total_ttc=Decimal("1200"),
        number="FA2026-00001",
    )
    payment = Payment.objects.create(
        company=company, invoice=invoice, direction="recu",
        date=date(2026, 1, 20), amount=Decimal("1200"), method="virement",
    )
    services.importer_csv(compte, "Date;Libellé;Montant\n20/01/2026;VIREMENT RECU;1200.00\n".encode())
    txn = BankTransaction.objects.first()
    suggestions = services.suggestions_rapprochement(txn)
    assert any(p.id == payment.id for p in suggestions)
    services.rapprocher(txn, payment, comptable_user)
    txn.refresh_from_db()
    assert txn.reconciled is True
    # Double rapprochement refusé
    with pytest.raises(BusinessError):
        services.rapprocher(txn, payment, comptable_user)


def test_rapprochement_montant_different_refuse(company, compte, comptable_user):
    client = Client.objects.create(company=company, code="C1", name="Client")
    invoice = Invoice.objects.create(
        company=company, client=client, status=InvoiceStatus.EMISE,
        issue_date=date(2026, 1, 5), due_date=date(2026, 2, 5),
        total_ttc=Decimal("999"), number="FA2026-1",
    )
    payment = Payment.objects.create(
        company=company, invoice=invoice, direction="recu",
        date=date(2026, 1, 20), amount=Decimal("999"), method="virement",
    )
    services.importer_csv(compte, "Date;Libellé;Montant\n20/01/2026;AUTRE;500.00\n".encode())
    txn = BankTransaction.objects.first()
    with pytest.raises(BusinessError) as exc:
        services.rapprocher(txn, payment, comptable_user)
    assert exc.value.code == "montant_different"


def test_previsionnel_structure(company, compte):
    client = Client.objects.create(company=company, code="C1", name="Client")
    invoice = Invoice.objects.create(
        company=company, client=client, status=InvoiceStatus.EMISE,
        issue_date=date.today(), due_date=date.today() + timedelta(days=20),
        total_ht=Decimal("1000"), total_vat=Decimal("200"), total_ttc=Decimal("1200"),
        number="FA-TEST",
    )
    for scenario in ("optimiste", "central", "prudent"):
        prev = services.previsionnel(company, scenario)
        assert len(prev["horizons"]) == 4
        assert [h["jours"] for h in prev["horizons"]] == [30, 60, 90, 180]
        assert prev["solde_initial"] == Decimal("1000")
    # Prudent < optimiste pour des encaissements attendus
    opt = services.previsionnel(company, "optimiste")
    pru = services.previsionnel(company, "prudent")
    assert Decimal(str(pru["horizons"][0]["solde_prevu"])) <= Decimal(str(opt["horizons"][0]["solde_prevu"]))
