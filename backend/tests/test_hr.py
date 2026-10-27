"""RH : employés, contrats, cycle de vie des absences."""

from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.core.exceptions import BusinessError
from apps.hr.models import Contract, Employee, LeaveBalance, LeaveRequest, LeaveType
from apps.hr.services import decider_absence, jours_ouvres

from .conftest import make_user

pytestmark = pytest.mark.django_db


def test_calcul_jours_ouvres():
    # Semaine du lundi 12 au vendredi 16/01/2026 = 5 jours
    assert jours_ouvres(date(2026, 1, 12), date(2026, 1, 16)) == 5
    # + week-end : identique
    assert jours_ouvres(date(2026, 1, 12), date(2026, 1, 18)) == 5
    # mi-journées
    assert jours_ouvres(date(2026, 1, 12), date(2026, 1, 16), True, True) == 4


def test_contrat_cdd_sans_fin_refuse(company, employee):
    contrat = Contract(
        employee=employee, contract_type="cdd", start_date=date(2026, 1, 1),
        weekly_hours=Decimal(35), gross_monthly_salary=Decimal("2500"),
    )
    with pytest.raises(Exception):
        contrat.clean()


def test_workflow_absence_complet(company, employee, rh_user, api_client):
    type_cp = LeaveType.objects.create(company=company, code="CP", label="Congés payés",
                                       annual_days=25)
    solde = LeaveBalance.objects.create(company=company, employee=employee, leave_type=type_cp,
                                        year=2026, acquired=25, taken=0)
    api_client.force_authenticate(rh_user)
    r = api_client.post(
        "/api/hr/leave-requests/",
        {
            "employee": employee.id,
            "leave_type": type_cp.id,
            "start_date": "2026-03-02",
            "end_date": "2026-03-06",
        },
        format="json",
    )
    assert r.status_code == 201
    demande = LeaveRequest.objects.get(pk=r.json()["id"])
    assert demande.business_days == 5  # calcul automatique serveur

    # Validation responsable
    r = api_client.post(f"/api/hr/leave-requests/{demande.id}/decision/", {"decision": "validee"},
                        format="json")
    assert r.status_code == 200
    solde.refresh_from_db()
    assert solde.taken == 5
    assert solde.remaining == 20

    # Double décision refusée
    r = api_client.post(f"/api/hr/leave-requests/{demande.id}/decision/", {"decision": "refusee"},
                        format="json")
    assert r.status_code == 400

    # Annulation recrédite le solde
    r = api_client.post(f"/api/hr/leave-requests/{demande.id}/annuler/", {}, format="json")
    assert r.status_code == 200
    solde.refresh_from_db()
    assert solde.taken == 0


def test_salarie_ne_decide_pas_sa_propre_absence(company, employee, salarie_user, api_client):
    type_cp = LeaveType.objects.create(company=company, code="CP", label="CP")
    salarie_user.employee_profile = None  # sécurité si pas de profil
    demande = LeaveRequest.objects.create(
        company=company, employee=employee, leave_type=type_cp,
        start_date=date(2026, 4, 1), end_date=date(2026, 4, 3), business_days=3,
        status="soumise",
    )
    api_client.force_authenticate(salarie_user)
    r = api_client.post(f"/api/hr/leave-requests/{demande.id}/decision/", {"decision": "validee"},
                        format="json")
    assert r.status_code == 403
