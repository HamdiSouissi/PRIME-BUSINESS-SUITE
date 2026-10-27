"""Budget annuel et pilotage (section 13 du cahier des charges)."""

from decimal import Decimal

from django.db import models

from apps.core.models import CompanyScopedModel


class Budget(CompanyScopedModel):
    """Budget annuel par compte de charge/produit (mois par mois)."""

    year = models.PositiveIntegerField("Année")
    label = models.CharField(max_length=128, default="Budget annuel")
    is_active = models.BooleanField(default=True)
    hypotheses = models.TextField(
        "Hypothèses documentées", blank=True, default="",
        help_text="Toute projection repose sur des hypothèses explicites.",
    )
    # Scénarios (JSON) : {"prudent": {"ca_variation_pct": -10}, ...}
    scenarios = models.JSONField("Scénarios de simulation", default=dict, blank=True)

    class Meta:
        unique_together = ("company", "year")

    def __str__(self):
        return f"{self.label} {self.year} — {self.company.name}"


class BudgetLine(CompanyScopedModel):
    NATURES = (
        ("produit", "Produit"),
        ("charge_fixe", "Charge fixe"),
        ("charge_variable", "Charge variable"),
        ("masse_salariale", "Masse salariale"),
    )

    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="lines")
    label = models.CharField(max_length=255)
    nature = models.CharField(max_length=20, choices=NATURES)
    account_prefix = models.CharField(
        "Préfixe de compte comptable pour le réalisé", max_length=8, blank=True, default="",
        help_text="Ex. 706 pour les prestations, 641 pour les salaires.",
    )
    monthly_amounts = models.JSONField(
        "Montants mensuels prévus (12 valeurs HT)",
        default=list,
        help_text='Ex. [1000, 1000, ...] — 12 valeurs numériques.',
    )

    def __str__(self):
        return f"{self.label} ({self.budget.year})"

    @property
    def total_annuel(self) -> Decimal:
        return sum(Decimal(str(v)) for v in (self.monthly_amounts or []))
