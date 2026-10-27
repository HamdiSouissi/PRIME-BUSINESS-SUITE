"""Abstraction des fournisseurs IA : Ollama (local) et API OpenAI-compatible.

- CodeCraftAPI : URL préremplie côté UI, GET /models pour découvrir les
  modèles, POST /chat/completions pour générer.
- Ollama : GET /api/tags pour lister les modèles, POST /api/chat.
- Aucun modèle volumineux n'est téléchargé automatiquement.
- Les secrets restent sur le serveur (jamais dans les réponses API).
"""

import logging
import time
from dataclasses import dataclass, field

import requests

from apps.core.exceptions import BusinessError
from apps.core.secrets import dechiffrer

from .models import AIProvider, AIUsageLog, ProviderKind

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    content: str
    model: str = ""
    tokens_input: int | None = None
    tokens_output: int | None = None
    raw: dict = field(default_factory=dict)


class ProviderClient:
    """Interface commune : test, modèles, génération de chat."""

    def __init__(self, provider: AIProvider):
        self.provider = provider
        self.base_url = (provider.base_url or "").rstrip("/")
        self.timeout = provider.timeout_seconds or 60

    # -- API standard -------------------------------------------------------
    def check(self) -> dict:
        raise NotImplementedError

    def list_models(self) -> list[dict]:
        raise NotImplementedError

    def chat(self, messages: list[dict], model: str = "", **kwargs) -> AIResponse:
        raise NotImplementedError


class OllamaClient(ProviderClient):
    def __init__(self, provider: AIProvider):
        super().__init__(provider)
        if not self.base_url:
            self.base_url = "http://localhost:11434"

    def check(self) -> dict:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=min(self.timeout, 15))
            response.raise_for_status()
            modeles = response.json().get("models", [])
            return {
                "ok": True,
                "detail": f"Serveur Ollama joignable — {len(modeles)} modèle(s) installé(s).",
                "modeles": [m.get("name", "") for m in modeles],
            }
        except requests.RequestException as exc:
            return {"ok": False, "detail": f"Serveur injoignable : {exc}"}

    def list_models(self) -> list[dict]:
        response = requests.get(f"{self.base_url}/api/tags", timeout=min(self.timeout, 15))
        response.raise_for_status()
        return [
            {"id": m.get("name", ""), "taille_octets": m.get("size", 0)}
            for m in response.json().get("models", [])
        ]

    def chat(self, messages, model: str = "", **kwargs) -> AIResponse:
        modele = model or self.provider.default_model
        if not modele:
            raise BusinessError(
                "Aucun modèle Ollama configuré (paramètres IA → fournisseurs).",
                code="modele_manquant",
            )
        payload = {"model": modele, "messages": messages, "stream": False}
        params = self.provider.generation_params or {}
        if params:
            payload["options"] = params
        try:
            response = requests.post(
                f"{self.base_url}/api/chat", json=payload, timeout=self.timeout
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise BusinessError(f"Ollama : erreur de génération : {exc}", code="ia_indisponible")
        data = response.json()
        return AIResponse(
            content=data.get("message", {}).get("content", ""),
            model=modele,
            tokens_input=data.get("prompt_eval_count"),
            tokens_output=data.get("eval_count"),
            raw={},
        )


class OpenAICompatibleClient(ProviderClient):
    """Client pour CodeCraftAPI et tout endpoint compatible OpenAI."""

    def _headers(self) -> dict:
        cle = dechiffrer(self.provider.api_key_encrypted)
        headers = {"Content-Type": "application/json"}
        if cle:
            headers["Authorization"] = f"Bearer {cle}"
        return headers

    def check(self) -> dict:
        try:
            response = requests.get(
                f"{self.base_url}/models", headers=self._headers(), timeout=min(self.timeout, 20)
            )
            response.raise_for_status()
            data = response.json()
            modeles = [m.get("id", "") for m in data.get("data", [])]
            return {"ok": True, "detail": f"API joignable — {len(modeles)} modèle(s).", "modeles": modeles}
        except requests.RequestException as exc:
            detail = getattr(exc.response, "text", "")[:300] if getattr(exc, "response", None) else str(exc)
            return {"ok": False, "detail": f"Échec de connexion : {type(exc).__name__}. {detail}"}

    def list_models(self) -> list[dict]:
        response = requests.get(
            f"{self.base_url}/models", headers=self._headers(), timeout=min(self.timeout, 20)
        )
        response.raise_for_status()
        return [
            {"id": m.get("id", ""), "proprietaire": m.get("owned_by", "")}
            for m in response.json().get("data", [])
        ]

    def chat(self, messages, model: str = "", **kwargs) -> AIResponse:
        modele = model or self.provider.default_model
        if not modele:
            raise BusinessError("Aucun modèle sélectionné.", code="modele_manquant")
        payload = {"model": modele, "messages": messages}
        payload.update(self.provider.generation_params or {})
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(), json=payload, timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise BusinessError(f"Fournisseur IA : erreur de génération : {exc}", code="ia_indisponible")
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise BusinessError("Réponse IA inattendue (format non conforme).", code="reponse_invalide")
        usage = data.get("usage", {}) or {}
        return AIResponse(
            content=content,
            model=data.get("model", modele),
            tokens_input=usage.get("prompt_tokens"),
            tokens_output=usage.get("completion_tokens"),
            raw={},
        )


def client_pour(provider: AIProvider) -> ProviderClient:
    if provider.kind == ProviderKind.OLLAMA:
        return OllamaClient(provider)
    return OpenAICompatibleClient(provider)


# ---------------------------------------------------------------------------
# Service applicatif principal
# ---------------------------------------------------------------------------

class AiUnavailable(BusinessError):
    pass


def obtenir_fournisseur(company, feature: str) -> AIProvider:
    """Résout le fournisseur d'une fonctionnalité, sinon le fournisseur actif
    par défaut. Lève AiUnavailable si l'IA n'est pas configurée/activée."""
    from .models import FeatureRouting

    routing = (
        FeatureRouting.objects.filter(company=company, feature=feature)
        .select_related("provider", "fallback_provider")
        .first()
    )
    if routing and routing.provider.is_enabled and routing.provider:
        return routing.provider
    provider = AIProvider.objects.filter(company=company, is_enabled=True).first()
    if provider is None:
        raise AiUnavailable(
            "L'assistant IA n'est pas activé. Configurez un fournisseur dans "
            "Paramètres → Intelligence artificielle (Ollama local disponible sans abonnement).",
            code="ia_desactivee",
        )
    return provider


def generer(company, feature: str, messages: list[dict], user=None, model: str = "") -> AIResponse:
    """Appel principal : génère une réponse IA pour une fonctionnalité, avec
    journalisation d'usage. Lève BusinessError si indisponible."""
    from .models import FeatureRouting

    t0 = time.monotonic()
    routing = FeatureRouting.objects.filter(company=company, feature=feature).select_related("provider", "fallback_provider").first()
    provider = routing.provider if routing and routing.provider.is_enabled else None
    model_name = (routing.model if routing else "") or model or (provider.default_model if provider else "")
    if provider is None:
        provider = obtenir_fournisseur(company, feature)

    client = client_pour(provider)
    try:
        reponse = client.chat(messages, model=model_name)
        succes, erreur = True, ""
    except BusinessError as exc:
        if routing and routing.fallback_provider and routing.fallback_provider.is_enabled:
            provider = routing.fallback_provider
            client = client_pour(provider)
            try:
                reponse = client.chat(messages, model=model_name or provider.default_model)
                succes, erreur = True, ""
            except BusinessError as exc2:
                reponse, succes, erreur = None, False, str(exc2)
        else:
            reponse, succes, erreur = None, False, str(exc)

    duration = int((time.monotonic() - t0) * 1000)
    AIUsageLog.objects.create(
        company=company,
        feature=feature,
        provider_kind=provider.kind,
        model=model_name,
        user=user,
        tokens_input=reponse.tokens_input if reponse else None,
        tokens_output=reponse.tokens_output if reponse else None,
        success=succes,
        error=erreur,
        duration_ms=duration,
    )
    if not succes:
        raise AiUnavailable(f"Fournisseur IA indisponible : {erreur}", code="ia_indisponible")
    return reponse
