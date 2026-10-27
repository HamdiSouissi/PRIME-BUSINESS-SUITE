"""Comptabilité : équilibre, immutabilité, exercices clôturés, rapports."""

from datetime import date
from decimal import Decimal

import pytest

from apps.accounting.models import EntryStatus, FiscalYear, JournalEntry
from apps.accounting.services import (
    balance_generale,
    bilan_simplifie,
    compte_de_resultat,
    contre_passer,
    creer_ecriture,
    valider_ecriture,
)
from apps.core.exceptions import BusinessError

pytestmark = pytest.mark.django_db


@pytest.mark.usefixtures("plan_comptable", "exercice")
def test_ecriture_equilibree_validee(company, comptable_user):
    entry = creer_ecriture(
        company, "VE", date(2026, 1, 15), "Vente test",
        [
            {"account": "411000", "label": "Client", "debit": "120", "credit": 0},
            {"account": "706000", "label": "Prestation", "debit": 0, "credit": "100"},
            {"account": "445710", "label": "TVA", "debit": 0, "credit": "20"},
        ],
        user=comptable_user,
    )
    assert entry.status == EntryStatus.VALIDEE
    assert entry.reference.startswith("VE-2026-")


@pytest.mark.usefixtures("plan_comptable", "exercice")
def test_ecriture_desquilibree_refusee(company, comptable_user):
    with pytest.raises(BusinessError) as exc:
        creer_ecriture(
            company, "VE", date(2026, 1, 15), "Mauvaise",
            [
                {"account": "411000", "debit": "120", "credit": 0},
                {"account": "706000", "debit": 0, "credit": "50"},  # ≠
            ],
            user=comptable_user,
        )
    assert exc.value.code == "ecriture_desquilibree"
    assert JournalEntry.objects.count() == 0


@pytest.mark.usefixtures("plan_comptable", "exercice")
def test_immutabilite_ecriture_validee(company, comptable_user, api_client):
    entry = creer_ecriture(
        company, "VE", date(2026, 1, 15), "Vente",
        [
            {"account": "411000", "debit": "120", "credit": 0},
            {"account": "706000", "debit": 0, "credit": "120"},
        ],
        user=comptable_user,
    )
    api_client.force_authenticate(comptable_user)
    # Modification interdite
    r = api_client.patch(f"/api/accounting/entries/{entry.id}/", {"label": "Modifié"}, format="json")
    assert r.status_code == 400
    # Suppression interdite
    r = api_client.delete(f"/api/accounting/entries/{entry.id}/")
    assert r.status_code == 400
    # La correction passe par une contre-passation
    reverse = contre_passer(entry, comptable_user, motif="Erreur de saisie")
    entry.refresh_from_db()
    assert entry.status == EntryStatus.CONTRE_PASSEE
    assert reverse.status == EntryStatus.VALIDEE


@pytest.mark.usefixtures("plan_comptable")
def test_exercice_cloture_bloque(company, comptable_user):
    fy = FiscalYear.objects.create(
        company=company, start_date=date(2025, 1, 1), end_date=date(2025, 12, 31), status="cloture"
    )
    with pytest.raises(BusinessError) as exc:
        creer_ecriture(
            company, "VE", date(2025, 6, 15), "Hors exercice",
            [
                {"account": "411000", "debit": "10", "credit": 0},
                {"account": "706000", "debit": 0, "credit": "10"},
            ],
            user=comptable_user,
        )
    assert exc.value.code == "exercice_cloture"


@pytest.mark.usefixtures("plan_comptable", "exercice")
def test_rapports_coherents(company, comptable_user):
    creer_ecriture(
        company, "VE", date(2026, 2, 1), "Vente",
        [
            {"account": "411000", "debit": "1200", "credit": 0},
            {"account": "706000", "debit": 0, "credit": "1000"},
            {"account": "445710", "debit": 0, "credit": "200"},
        ],
        user=comptable_user,
    )
    creer_ecriture(
        company, "AC", date(2026, 2, 3), "Achat",
        [
            {"account": "606100", "debit": "300", "credit": 0},
            {"account": "445660", "debit": "60", "credit": 0},
            {"account": "401000", "debit": 0, "credit": "360"},
        ],
        user=comptable_user,
    )
    fy = FiscalYear.objects.get(company=company)
    balance = balance_generale(company, fy)
    # La balance est équilibrée en total
    total_debit = sum(l["debit"] for l in balance)
    total_credit = sum(l["credit"] for l in balance)
    assert total_debit == total_credit == Decimal("1560")

    cr = compte_de_resultat(company, fy)
    assert cr["total_produits"] == Decimal("1000")
    assert cr["total_charges"] == Decimal("300")
    assert cr["resultat"] == Decimal("700")

    bilan = bilan_simplifie(company, fy)
    assert "resultat" in bilan["passif"]
    # Export de préparation : entête + 6 lignes (3 par écriture)
    from apps.accounting.services import export_fec

    fec = export_fec(company, fy)
    assert fec.count("\r\n") == 7


@pytest.mark.usefixtures("plan_comptable", "exercice")
def test_journal_inconnu_refuse(company, comptable_user):
    with pytest.raises(BusinessError) as exc:
        creer_ecriture(
            company, "XX", date(2026, 1, 15), "Test",
            [{"account": "411000", "debit": "1", "credit": 0},
             {"account": "706000", "debit": 0, "credit": "1"}],
        )
    assert exc.value.code == "journal_inconnu"
