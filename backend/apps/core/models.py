"""Modèles transverses : bases abstraites, séquences, journal d'audit."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


class TimeStampedModel(models.Model):
    """Base commune : horodatage de création et de modification."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CompanyScopedModel(TimeStampedModel):
    """Modèle rattaché à une entreprise (isolation des données).

    Tout enregistrement métier appartient à une `Company`. Le filtrage est
    appliqué côté serveur via `CompanyFilterBackend`.
    """

    company = models.ForeignKey(
        "organization.Company",
        on_delete=models.CASCADE,
        related_name="+",
    )

    class Meta:
        abstract = True


class Sequence(models.Model):
    """Compteur de numérotation contrôlée (factures, bulletins, écritures…).

    L'incrément se fait sous verrou de ligne (`select_for_update`) dans une
    transaction pour garantir l'absence de trous concurrents et de doublons.
    """

    company = models.ForeignKey(
        "organization.Company", on_delete=models.CASCADE, related_name="sequences"
    )
    key = models.CharField(max_length=64)
    prefix = models.CharField(max_length=16, blank=True, default="")
    year = models.PositiveIntegerField(null=True, blank=True)
    next_value = models.PositiveBigIntegerField(default=1)
    padding = models.PositiveSmallIntegerField(default=5)

    class Meta:
        unique_together = ("company", "key", "year")

    def __str__(self):
        return f"{self.key} ({self.company}) — prochain : {self.next_value}"

    @classmethod
    @transaction.atomic
    def allocate(cls, company, key: str, prefix: str = "", year: int | None = None,
                 padding: int = 5) -> str:
        """Retourne le prochain numéro formaté et incrémente le compteur."""
        sequence, _ = (
            cls.objects.select_for_update()
            .get_or_create(
                company=company,
                key=key,
                year=year,
                defaults={"prefix": prefix, "padding": padding},
            )
        )
        value = sequence.next_value
        sequence.next_value = models.F("next_value") + 1
        sequence.save(update_fields=["next_value"])
        stem = f"{prefix}{year}-" if year else prefix
        return f"{stem}{value:0{sequence.padding}d}"


class AuditLog(models.Model):
    """Journal d'audit : qui a fait quoi, quand, depuis où."""

    SENSIBILITES = (
        ("info", "Information"),
        ("securite", "Sécurité"),
        ("paie", "Paie"),
        ("finance", "Finance"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    company = models.ForeignKey(
        "organization.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=255)
    detail = models.TextField(blank=True, default="")
    method = models.CharField(max_length=8, blank=True, default="")
    path = models.CharField(max_length=500, blank=True, default="")
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    sensitivity = models.CharField(max_length=16, choices=SENSIBILITES, default="info")

    class Meta:
        ordering = ("-occurred_at",)
        indexes = [
            models.Index(fields=["company", "occurred_at"]),
            models.Index(fields=["user", "occurred_at"]),
        ]

    def __str__(self):
        return f"[{self.occurred_at:%Y-%m-%d %H:%M}] {self.action}"

    def delete(self, *args, **kwargs):  # pragma: no cover - garde-fou
        raise ValidationError("Les journaux d'audit ne sont pas supprimables.")


class DocumentFile(CompanyScopedModel):
    """Fichier attaché générique (justificatif, pièce comptable, contrat…)."""

    CATEGORIES = (
        ("justificatif", "Justificatif"),
        ("contrat", "Contrat"),
        ("bulletin", "Bulletin de paie"),
        ("facture", "Facture"),
        ("banque", "Relevé bancaire"),
        ("administratif", "Document administratif"),
        ("autre", "Autre"),
    )

    label = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=CATEGORIES, default="autre")
    file = models.FileField(upload_to="documents/%Y/%m/")
    content_type = models.CharField(max_length=100, blank=True, default="")
    size = models.PositiveBigIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    # Lien souple vers l'objet métier d'origine (sans clé étrangère croisée).
    linked_model = models.CharField(max_length=64, blank=True, default="")
    linked_id = models.PositiveBigIntegerField(null=True, blank=True)

    def __str__(self):
        return self.label
