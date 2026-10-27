"""Bibliothèque de modèles de documents et génération (section 10)."""

from django.conf import settings
from django.db import models

from apps.core.models import CompanyScopedModel, TimeStampedModel


class TemplateType(models.TextChoices):
    CONTRAT_TRAVAIL = "contrat_travail", "Contrat de travail"
    AVENANT = "avenant", "Avenant"
    EMBAUCHE = "embauche", "Document d'embauche"
    FIN_CONTRAT = "fin_contrat", "Document de fin de contrat"
    PRESTATION = "prestation", "Contrat de prestation"
    MAINTENANCE = "maintenance", "Contrat de maintenance"
    ABONNEMENT = "abonnement", "Contrat d'abonnement"
    CGV = "cgv", "Conditions commerciales"
    PV = "pv", "Procès-verbal / décision sociale"
    AUTRE = "autre", "Autre"


class TemplateStatus(models.TextChoices):
    BROUILLON = "brouillon", "Brouillon"
    VALIDE = "valide", "Validé juridiquement"
    ARCHIVE = "archive", "Archivé"


class DocumentTemplate(CompanyScopedModel):
    """Modèle de document versionné avec champs dynamiques {{variable}}."""

    template_type = models.CharField(max_length=20, choices=TemplateType.choices)
    name = models.CharField("Nom du modèle", max_length=255)
    version = models.PositiveIntegerField(default=1)
    content = models.TextField(
        "Contenu avec champs dynamiques",
        help_text="Variables disponibles au format {{variable}}.",
    )
    status = models.CharField(max_length=16, choices=TemplateStatus.choices, default=TemplateStatus.BROUILLON)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    legal_review_note = models.TextField(
        "Note de validation juridique", blank=True, default="",
        help_text="Toute production finale exige une relecture juridique tracée.",
    )
    supersedes = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="suivant"
    )

    class Meta:
        unique_together = ("company", "name", "version")
        ordering = ("template_type", "name", "-version")

    def __str__(self):
        return f"{self.name} v{self.version}"


class GeneratedDocumentStatus(models.TextChoices):
    BROUILLON = "brouillon", "Brouillon (relecture requise)"
    VALIDE = "valide", "Validé en interne"
    EN_SIGNATURE = "signature", "Envoyé en signature"
    SIGNE = "signe", "Signé (preuve conservée)"
    ARCHIVE = "archive", "Archivé"


class GeneratedDocument(CompanyScopedModel):
    """Document généré depuis un modèle — instantané figé du contenu."""

    template = models.ForeignKey(DocumentTemplate, on_delete=models.PROTECT, related_name="documents")
    label = models.CharField(max_length=255)
    status = models.CharField(
        max_length=16, choices=GeneratedDocumentStatus.choices, default=GeneratedDocumentStatus.BROUILLON
    )
    # Instantané : le contenu n'évolue plus après génération
    content_snapshot = models.TextField()
    context_data = models.JSONField("Données utilisées", default=dict)
    pdf = models.FileField(upload_to="documents/generated/%Y/%m/", null=True, blank=True)
    target_employee = models.ForeignKey(
        "hr.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    target_client = models.ForeignKey(
        "invoicing.Client", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # IA : brouillon généré par IA → relecture humaine obligatoire
    ai_draft = models.BooleanField("Brouillon généré par IA", default=False)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    # Suivi de signature électronique (intégration externe)
    signature_provider = models.CharField("Prestataire de signature", max_length=128, blank=True, default="")
    signature_external_id = models.CharField("Identifiant externe", max_length=128, blank=True, default="")
    signature_proof = models.JSONField("Preuve de signature", default=dict, blank=True)
    alert_before_date = models.DateField("Alerte d'échéance", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ("-created_at",)
