"""Centre de conformité : obligations réglementaires (section 14).

Chaque règle déclarée porte sa SOURCE officielle, sa date de vérification et
sa période de validité. Aucune obligation n'est présentée comme universelle :
l'applicabilité est calculée selon le statut, l'effectif et le régime de TVA
de l'entreprise.
"""

from datetime import date

from django.conf import settings
from django.db import models

from apps.core.models import CompanyScopedModel, TimeStampedModel


class ObligationCategory(models.TextChoices):
    SOCIALE = "sociale", "Échéance sociale"
    FISCALE = "fiscale", "Échéance fiscale"
    COMPTABLE = "comptable", "Obligation comptable"
    CONTRACTUELLE = "contractuelle", "Échéance contractuelle"
    DOCUMENTAIRE = "documentaire", "Conservation documentaire"
    AUTRE = "autre", "Autre"


class Periodicity(models.TextChoices):
    MENSUELLE = "mensuelle", "Mensuelle"
    TRIMESTRIELLE = "trimestrielle", "Trimestrielle"
    SEMESTRIELLE = "semestrielle", "Semestrielle"
    ANNUELLE = "annuelle", "Annuelle"
    PONCTUELLE = "ponctuelle", "Ponctuelle"


class ObligationDefinition(TimeStampedModel):
    """Catalogue GLOBAL des règles (même table pour toutes les entreprises ;
    l'applicabilité est évaluée après selon la configuration de chacune)."""

    code = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=ObligationCategory.choices)
    periodicity = models.CharField(max_length=20, choices=Periodicity.choices)
    # Jour d'échéance dans le mois / date annuelle (mois-jour)
    due_day = models.PositiveSmallIntegerField("Jour d'échéance", default=15)
    due_month = models.PositiveSmallIntegerField("Mois d'échéance (si annuelle)", null=True, blank=True)
    description = models.TextField(blank=True, default="")
    # Applicabilité (JSON) : formes juridiques, régimes TVA, effectif min…
    applicability = models.JSONField(
        default=dict,
        help_text=(
            'Ex. {"legal_forms": ["sas","sasu"], "vat_regimes": ["reel_normal"], '
            '"headcount_min": 1}. Vide = applicable à tous (avec prudence).'
        ),
    )
    source_url = models.URLField("Source officielle", blank=True, default="")
    source_label = models.CharField("Référence de la source", max_length=255, blank=True, default="")
    verified_at = models.DateField("Date de vérification", null=True, blank=True)
    valid_until = models.DateField("Validité jusqu'au", null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("category", "label")

    def __str__(self):
        return self.label

    def is_applicable_to(self, company) -> bool:
        """Évalue l'applicabilité réelle à une entreprise donnée."""
        rules = self.applicability or {}
        if not rules:
            return True
        formes = rules.get("legal_forms")
        if formes and company.legal_form not in formes:
            return False
        regimes = rules.get("vat_regimes")
        if regimes and company.vat_regime not in regimes:
            return False
        headcount_min = rules.get("headcount_min")
        if headcount_min is not None and company.headcount < headcount_min:
            return False
        headcount_max = rules.get("headcount_max")
        if headcount_max is not None and company.headcount > headcount_max:
            return False
        return True


class ObligationInstance(CompanyScopedModel):
    """Occurrence concrète d'une obligation pour une entreprise."""

    STATUTS = (
        ("a_faire", "À faire"),
        ("en_cours", "En cours"),
        ("faite", "Faite (preuve attachée)"),
        ("non_applicable", "Non applicable"),
        ("depassee", "Dépassée"),
    )

    definition = models.ForeignKey(ObligationDefinition, on_delete=models.CASCADE, related_name="instances")
    due_date = models.DateField()
    status = models.CharField(max_length=16, choices=STATUTS, default="a_faire")
    completed_at = models.DateField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    proof = models.FileField("Preuve / justificatif", upload_to="conformite/%Y/", null=True, blank=True)
    note = models.TextField(blank=True, default="")

    class Meta:
        unique_together = ("company", "definition", "due_date")
        ordering = ("due_date",)

    @property
    def days_late(self) -> int:
        today = date.today()
        return max(0, (today - self.due_date).days) if self.status in {"a_faire", "en_cours"} else 0
