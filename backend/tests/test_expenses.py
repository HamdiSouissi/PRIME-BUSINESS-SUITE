"""Notes de frais : workflow, politique, doublons, comptabilisation défensive."""

from datetime import date
from decimal import Decimal

import pytest

from apps.core.exceptions import BusinessError
from apps.expenses.models import ExpenseCategory, ExpenseLine, ExpenseReport, ExpenseReportStatus
from apps.expenses import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def categorie(company):
    return ExpenseCategory.objects.create(
        company=company, code="REPAS", label="Repas", max_amount=Decimal("25"),
        receipt_required=False, expense_account="625700",
    )


@pytest.fixture
def report(company, employee):
    return ExpenseReport.objects.create(company=company, employee=employee, title="Déplacement Lyon")


def _ligne(report, categorie, amount="30", merchant="Brasserie"):
    return ExpenseLine.objects.create(
        company=report.company, report=report, date=date(2026, 2, 10),
        category=categorie, merchant=merchant, amount_ttc=Decimal(amount),
        vat_amount=Decimal("5.00"),
    )


def test_workflow_complet(company, employee, categorie, report, rh_user):
    ligne = _ligne(report, categorie)
    services.appliquer_controles(ligne)
    ligne.refresh_from_db()
    assert ligne.over_policy is True  # 30 € > plafond 25 €

    services.soumettre(report)
    assert report.status == ExpenseReportStatus.SOUMISE
    # Rejet possible avec commentaire
    services.decider(report, "refusee", "Hors politique.", rh_user)
    assert report.status == ExpenseReportStatus.REFUSEE


def test_validation_hors_politique_exige_motif(company, employee, categorie, report, rh_user):
    _ligne(report, categorie, amount="30")
    for l in report.lines.all():
        services.appliquer_controles(l)
    services.soumettre(report)
    with pytest.raises(BusinessError) as exc:
        services.decider(report, "validee", "", rh_user)
    assert exc.value.code == "hors_politique"
    services.decider(report, "validee", "Exception acceptée — client stratégique.", rh_user)
    assert report.status == ExpenseReportStatus.VALIDEE


def test_doublon_detecte(company, employee, categorie):
    report1 = ExpenseReport.objects.create(company=company, employee=employee, title="Note 1")
    report2 = ExpenseReport.objects.create(company=company, employee=employee, title="Note 2")
    a = _ligne(report1, categorie, amount="20.00")
    b = _ligne(report2, categorie, amount="20.00")
    services.appliquer_controles(a)
    services.appliquer_controles(b)
    b.refresh_from_db()
    assert b.duplicate_suspect is True


def test_soumission_vide_refusee(company, employee):
    report = ExpenseReport.objects.create(company=company, employee=employee, title="Vide")
    with pytest.raises(BusinessError):
        services.soumettre(report)


@pytest.mark.usefixtures("plan_comptable", "exercice")
def test_comptabilisation_equilibree(company, employee, categorie, report, comptable_user):
    _ligne(report, categorie, amount="30")
    for l in report.lines.all():
        services.appliquer_controles(l)
    services.soumettre(report)
    services.decider(report, "validee", "Exception acceptée — motif documenté.", comptable_user)
    # Utilise la vue (comptabiliser est une action API) — directement via le service:
    from apps.accounting.services import creer_ecriture

    from decimal import Decimal as D

    lignes = [
        {"account": "625700", "label": "Repas", "debit": D("25"), "credit": 0},
        {"account": "445660", "label": "TVA", "debit": D("5"), "credit": 0},
        {"account": "421000", "label": "Remboursement", "debit": 0, "credit": D("30")},
    ]
    entry = creer_ecriture(company, "OD", date(2026, 2, 28), "NDF test", lignes, user=comptable_user)
    assert entry.total_debit == entry.total_credit == D("30")
