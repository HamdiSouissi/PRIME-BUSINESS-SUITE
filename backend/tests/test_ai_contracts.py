"""IA : secrets protégés, tolérance aux pannes, fournisseurs ; contrats."""

from unittest.mock import patch

import pytest

from apps.ai_assistant.models import AIProvider, AIFeature, ProviderKind
from apps.ai_assistant.providers import AiUnavailable, OpenAICompatibleClient, generer
from apps.core.exceptions import BusinessError
from apps.core.secrets import chiffrer, dechiffrer
from apps.contracts.models import DocumentTemplate, TemplateStatus, TemplateType
from apps.contracts import services as doc_services

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Secrets chiffrés
# ---------------------------------------------------------------------------

def test_secret_chiffre_dechiffrable():
    token = chiffrer("sk-super-secret")
    assert token != "sk-super-secret"
    assert dechiffrer(token) == "sk-super-secret"


def test_cle_jamais_exposee_dans_api(company, admin_user, api_client):
    AIProvider.objects.create(
        company=company, kind=ProviderKind.CODECRAFT, label="CodeCraftAPI",
        base_url="https://codecraftapi.com/v1",
        api_key_encrypted=chiffrer("sk-secret-123"), is_enabled=True,
    )
    api_client.force_authenticate(admin_user)
    r = api_client.get("/api/ai/providers/")
    assert r.status_code == 200
    payload = r.json()
    assert "sk-secret-123" not in str(payload)
    fournisseur = payload["results"][0]
    assert fournisseur["api_key_defined"] is True
    assert "api_key_encrypted" not in fournisseur


def test_ia_desactivee_refuse_gracieusement(company, admin_user):
    """Aucune fonction IA quand aucun fournisseur actif → BusinessError 503."""
    with pytest.raises(AiUnavailable):
        generer(company, AIFeature.RESUME_DOCUMENT, [{"role": "user", "content": "test"}], admin_user)


def test_api_ia_indisponible_503(company, admin_user, api_client):
    api_client.force_authenticate(admin_user)
    r = api_client.post("/api/ai/assist/", {"action": "resumer_document", "data": {"texte": "doc"}},
                        format="json")
    assert r.status_code == 503


class _FakeResponse:
    def __init__(self, payload, code=200):
        self._payload = payload
        self.status_code = code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_client_openai_compatible_generation(company, admin_user):
    provider = AIProvider.objects.create(
        company=company, kind=ProviderKind.CODECRAFT, label="CodeCraftAPI",
        base_url="https://codecraftapi.com/v1",
        api_key_encrypted=chiffrer("sk-test"), is_enabled=True,
        default_model="gpt-test",
    )
    payload = {
        "choices": [{"message": {"content": "Réponse simulée"}}],
        "model": "gpt-test",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    with patch("apps.ai_assistant.providers.requests.post", return_value=_FakeResponse(payload)) as post:
        reponse = generer(
            company, AIFeature.RESUME_DOCUMENT,
            [{"role": "user", "content": "Document à résumer"}], admin_user,
        )
    assert reponse.content == "Réponse simulée"
    assert reponse.tokens_input == 10
    # La clé part dans l'en-tête Authorization, invisible en réponse
    headers = post.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer sk-test"
    # Journal d'usage écrit
    from apps.ai_assistant.models import AIUsageLog

    assert AIUsageLog.objects.filter(company=company, success=True).count() == 1


def test_echec_fournisseur_journalise(company, admin_user):
    AIProvider.objects.create(
        company=company, kind=ProviderKind.CODECRAFT, label="CodeCraftAPI",
        base_url="https://codecraftapi.invalid/v1", is_enabled=True, default_model="x",
    )
    with patch(
        "apps.ai_assistant.providers.requests.post",
        side_effect=__import__("requests").ConnectionError("DNS"),
    ):
        with pytest.raises(AiUnavailable):
            generer(company, AIFeature.RESUME_DOCUMENT, [{"role": "user", "content": "t"}], admin_user)
    from apps.ai_assistant.models import AIUsageLog

    assert AIUsageLog.objects.filter(company=company, success=False).exists()


# ---------------------------------------------------------------------------
# Documents / contrats
# ---------------------------------------------------------------------------

def _template(company, status=TemplateStatus.VALIDE):
    return DocumentTemplate.objects.create(
        company=company, template_type=TemplateType.PRESTATION, name="Contrat de prestation",
        version=1, status=status,
        content="Entre {{societe}} et {{client}} — montant {{montant}} € HT. Signature : {{lieu}}.",
    )


def test_generation_exige_modele_valide(company, admin_user):
    template = _template(company, status=TemplateStatus.BROUILLON)
    with pytest.raises(BusinessError) as exc:
        doc_services.generer_document(template, {"societe": "PVS"}, admin_user, "test")
    assert exc.value.code == "modele_non_valide"


def test_substitution_variables(company, admin_user):
    template = _template(company)
    document = doc_services.generer_document(
        template,
        {"societe": "Prime Vision Solutions", "client": "ACME", "montant": "12000"},
        admin_user, "Contrat ACME",
    )
    assert "Prime Vision Solutions" in document.content_snapshot
    assert "ACME" in document.content_snapshot
    # Champ manquant → balise explicite, jamais une chaîne vide silencieuse
    assert "[lieu — À COMPLÉTER]" in document.content_snapshot


def test_document_pdf_et_docx(company, admin_user):
    template = _template(company)
    document = doc_services.generer_document(
        template, {"societe": "PVS", "client": "ACME", "montant": "100", "lieu": "Paris"},
        admin_user, "Contrat",
    )
    doc_services.generer_pdf(document)
    assert document.pdf
    with document.pdf.open("rb") as f:
        assert f.read(4) == b"%PDF"
    docx = doc_services.generer_docx(document)
    assert docx[:2] == b"PK"  # archive DOCX


def test_versioning_modele(company, admin_user):
    template = _template(company)
    # Brouillon IA : validation humaine obligatoire
    document = doc_services.generer_document(
        template, {"societe": "PVS", "client": "X", "montant": "1", "lieu": "Lyon"},
        admin_user, "Doc IA", ai_draft=True,
    )
    assert document.status == "brouillon"
    doc_services.valider_document(document, admin_user)
    document.refresh_from_db()
    assert document.status == "valide"
    with pytest.raises(BusinessError):
        doc_services.valider_document(document, admin_user)
