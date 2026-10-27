"""Authentification, permissions et isolation des données entre entreprises."""

import pytest
from rest_framework.test import APIClient

from apps.core.permissions import Roles
from apps.invoicing.models import Client

from .conftest import make_user

pytestmark = pytest.mark.django_db


def test_login_ok(company, admin_user, api_client):
    r = api_client.post(
        "/api/auth/login/",
        {"email": "admin@test.example", "password": "Test1234!pass"},
        format="json",
    )
    assert r.status_code == 200
    assert "access" in r.json() and "refresh" in r.json()


def test_login_mot_de_passe_incorrect(company, admin_user, api_client):
    r = api_client.post(
        "/api/auth/login/", {"email": "admin@test.example", "password": "mauvais"}, format="json"
    )
    assert r.status_code == 401


def test_blocage_apres_echecs(company, admin_user, api_client, settings):
    settings.LOGIN_MAX_ATTEMPTS = 3
    settings.LOGIN_LOCK_MINUTES = 1
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    for _ in range(3):
        api_client.post(
            "/api/auth/login/", {"email": "admin@test.example", "password": "x"}, format="json"
        )
    r = api_client.post(
        "/api/auth/login/",
        {"email": "admin@test.example", "password": "Test1234!pass"},
        format="json",
    )
    assert r.status_code == 429


def test_isolation_entreprises(company, autre_company, admin_user, api_client):
    """Un utilisateur de A ne voit jamais les clients de B."""
    Client.objects.create(company=autre_company, code="AUTRE", name="Client de B")
    api_client.force_authenticate(admin_user)
    r = api_client.get("/api/invoicing/clients/")
    assert r.status_code == 200
    noms = [c["name"] for c in r.json()["results"]]
    assert "Client de B" not in noms


def test_ecriture_choisit_entreprise_active(company, admin_user, api_client):
    api_client.force_authenticate(admin_user)
    r = api_client.post(
        "/api/invoicing/clients/", {"code": "C01", "name": "Client A"}, format="json"
    )
    assert r.status_code == 201
    assert Client.objects.get(code="C01").company == company


def test_salarie_ne_liste_pas_les_utilisateurs(company, salarie_user, api_client):
    api_client.force_authenticate(salarie_user)
    r = api_client.get("/api/accounts/users/")
    assert r.status_code == 403


def test_access_anonyme_refuse(api_client):
    r = api_client.get("/api/dashboard/")
    assert r.status_code == 401


def test_roles_differents_permissions_differentes(company, rh_user, api_client):
    """Le rôle RH ne peut pas accéder au journal d'audit (réservé admin/direction)."""
    api_client.force_authenticate(rh_user)
    r = api_client.get("/api/audit/")
    assert r.status_code == 403
