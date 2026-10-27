"""Assistant IA facultatif : fournisseurs, routage par fonction, journal.

Principes (section 15) :
- IA locale (Ollama) par défaut ; fournisseurs externes (CodeCraftAPI…) strictement
  facultatifs.
- Aucune API payante n'est requise pour les fonctions essentielles.
- Les clés API sont chiffrées et jamais exposées au client.
- L'IA ne décide jamais seule d'une paie, d'un paiement ou d'une déclaration :
  les fonctions IA produisent des BROUILLONS ou des synthèses à valider.
- L'application reste pleinement fonctionnelle si l'IA est désactivée.
"""

from django.conf import settings
from django.db import models

from apps.core.models import CompanyScopedModel, TimeStampedModel


class ProviderKind(models.TextChoices):
    OLLAMA = "ollama", "Ollama (local)"
    CODECRAFT = "codecraftapi", "CodeCraftAPI"
    OPENAI_COMPAT = "openai_compatible", "Compatible OpenAI (auto-hébergé)"


class AIProvider(CompanyScopedModel):
    """Configuration d'un fournisseur IA (clé chiffrée côté serveur)."""

    kind = models.CharField(max_length=20, choices=ProviderKind.choices)
    label = models.CharField(max_length=128, default="Fournisseur IA")
    base_url = models.URLField("URL de base", blank=True, default="")
    api_key_encrypted = models.TextField("Clé API (chiffrée)", blank=True, default="")
    default_model = models.CharField("Modèle par défaut", max_length=128, blank=True, default="")
    is_enabled = models.BooleanField("Activé", default=False)
    # Paramètres de génération compatibles
    generation_params = models.JSONField(
        default=dict, blank=True,
        help_text='Ex. {"temperature": 0.2, "max_tokens": 1024}',
    )
    timeout_seconds = models.PositiveSmallIntegerField("Délai maximal (s)", default=60)
    # État de disponibilité (mis à jour par le test de connexion)
    last_status = models.CharField("Dernier statut", max_length=32, blank=True, default="")
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField("Dernière erreur", blank=True, default="")
    # Modèles découverts (cache depuis GET /models)
    available_models = models.JSONField(default=list, blank=True)
    billing_info = models.TextField("Tarification / consommation", blank=True, default="")

    class Meta:
        unique_together = ("company", "kind")
        ordering = ("kind",)

    def __str__(self):
        return f"{self.label} ({self.get_kind_display()})"


class AIFeature(models.TextChoices):
    EXTRACTION_FACTURE = "extraction_facture", "Extraction de données de facture"
    RESUME_DOCUMENT = "resume_document", "Résumé de document"
    BROUILLON_CONTRAT = "brouillon_contrat", "Brouillon de contrat"
    REDACTION_EMAIL = "redaction_email", "Rédaction d'e-mail"
    SYNTHESE_TRESORERIE = "synthese_tresorerie", "Synthèse de trésorerie"
    EXPLICATION_INDICATEUR = "explication_indicateur", "Explication d'indicateur financier"
    ANOMALIES = "anomalies", "Détection d'anomalies à vérifier"
    RAPPORT = "rapport", "Préparation de rapport"
    RECHERCHE_NL = "recherche_nl", "Recherche en langage naturel"
    CLASSIFICATION_DEPENSE = "classification_depense", "Classification des dépenses"


class FeatureRouting(CompanyScopedModel):
    """Choix du fournisseur et du modèle pour chaque fonctionnalité IA."""

    feature = models.CharField(max_length=32, choices=AIFeature.choices)
    provider = models.ForeignKey(AIProvider, on_delete=models.CASCADE, related_name="routages")
    model = models.CharField(max_length=128, blank=True, default="")
    fallback_provider = models.ForeignKey(
        AIProvider, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        unique_together = ("company", "feature")


class AIUsageLog(CompanyScopedModel):
    """Journal des appels IA : fonctionnalité, fournisseur, volume, coût éventuel."""

    feature = models.CharField(max_length=32)
    provider_kind = models.CharField(max_length=20)
    model = models.CharField(max_length=128, blank=True, default="")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    tokens_input = models.PositiveIntegerField(null=True, blank=True)
    tokens_output = models.PositiveIntegerField(null=True, blank=True)
    success = models.BooleanField(default=True)
    error = models.TextField(blank=True, default="")
    duration_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
