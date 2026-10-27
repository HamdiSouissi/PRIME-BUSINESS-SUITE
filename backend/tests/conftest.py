"""Fixtures partagées de la suite de tests."""

import pytest
from datetime import date
from decimal import Decimal

from apps.accounts.models import CompanyMembership, User
from apps.accounting.models import FiscalYear
from apps.accounting.seed_pcg import peupler_plan_comptable
from apps.core.permissions import Roles
from apps.organization.models import Company


@pytest.fixture
def company(db):
    return Company.objects.create(
        name="Société Test SAS",
        legal_form="sas",
        siret="12345678900012",
        siren="123456789",
        share_capital=Decimal("10000"),
        vat_regime="reel_normal",
        headcount=3,
        city="Paris",
        collective_agreement="Syntec",
    )


@pytest.fixture
def autre_company(db):
    return Company.objects.create(
        name="Autre Société",
        legal_form="sasu",
        siret="99988877700010",
        siren="999888777",
        share_capital=Decimal("1000"),
        vat_regime="franchise",
        headcount=1,
    )


def make_user(email, company, role, password="Test1234!pass"):
    user = User.objects.create_user(
        username=email.split("@")[0], email=email, password=password,
        first_name="Test", last_name=role,
    )
    CompanyMembership.objects.create(user=user, company=company, role=role)
    return user


@pytest.fixture
def admin_user(company):
    return make_user("admin@test.example", company, Roles.ADMIN)


@pytest.fixture
def paie_user(company):
    return make_user("paie@test.example", company, Roles.PAIE)


@pytest.fixture
def comptable_user(company):
    return make_user("comptable@test.example", company, Roles.COMPTABLE)


@pytest.fixture
def rh_user(company):
    return make_user("rh@test.example", company, Roles.RH)


@pytest.fixture
def salarie_user(company):
    return make_user("salarie@test.example", company, Roles.SALARIE)


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def auth_client(api_client, admin_user):
    api_client.force_authenticate(admin_user)
    return api_client


def client_for(api_client, user):
    api_client.force_authenticate(user)
    return api_client


@pytest.fixture
def exercice(company):
    return FiscalYear.objects.create(
        company=company, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)
    )


@pytest.fixture
def plan_comptable(company):
    peupler_plan_comptable(company)


@pytest.fixture
def employee(company):
    from apps.hr.models import Contract, Employee

    emp = Employee.objects.create(
        company=company,
        matricule="T001",
        first_name="Jeanne",
        last_name="Essai",
        hire_date=date(2024, 3, 1),
        status="actif",
        social_security_number="123456789012345",
        bank_iban="FR7612345678901234567890123",
        email_pro="jeanne@test.example",
    )
    Contract.objects.create(
        employee=emp,
        contract_type="cdi",
        start_date=date(2024, 3, 1),
        weekly_hours=Decimal("35"),
        gross_monthly_salary=Decimal("2500.00"),
        is_cadre=False,
        withholding_rate=Decimal("5"),
    )
    return emp


@pytest.fixture
def ruleset(company, admin_user):
    """Jeu de règles 2025 provisoire puis basculable en vérifié."""
    from apps.payroll.services import creer_ruleset_reference

    return creer_ruleset_reference(company, admin_user)


@pytest.fixture
def ruleset_verifie(ruleset, admin_user):
    from django.utils import timezone

    from apps.payroll.models import RulesetStatus

    ruleset.status = RulesetStatus.VERIFIE
    ruleset.verified_by = admin_user
    ruleset.verified_at = timezone.now()
    ruleset.verification_note = "Cas de test."
    ruleset.save()
    return ruleset
