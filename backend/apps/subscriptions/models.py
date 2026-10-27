"""Abonnements et revenus récurrents (section 9 du cahier des charges)."""

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import CompanyScopedModel


class SubscriptionStatus(models.TextChoices):
    ACTIF = "actif", "Actif"
    ESSAI = "essai", "Période d'essai"
    SUSPENDU = "suspendu", "Suspendu"
    RESILIE = "resilie", "Résilié"


class Periodicity(models.TextChoices):
    MENSUEL = "mensuel", "Mensuel"
    TRIMESTRIEL = "trimestriel", "Trimestriel"
    ANNUEL = "annuel", "Annuel"


# Durée de chaque périodicité en mois (hors enum, qui refuserait un dict)
PERIODICITE_MOIS = {"mensuel": 1, "trimestriel": 3, "annuel": 12}


class Subscription(CompanyScopedModel):
    client = models.ForeignKey("invoicing.Client", on_delete=models.PROTECT, related_name="abonnements")
    label = models.CharField("Libellé du service", max_length=255)
    status = models.CharField(max_length=16, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIF)
    periodicity = models.CharField(max_length=16, choices=Periodicity.choices, default=Periodicity.MENSUEL)
    price_ht = models.DecimalField("Prix HT par période", max_digits=12, decimal_places=2)
    vat_rate = models.DecimalField("TVA (%)", max_digits=5, decimal_places=2, default="20")
    discount_percent = models.DecimalField("Remise (%)", max_digits=5, decimal_places=2, default=0)
    start_date = models.DateField("Début")
    end_date = models.DateField("Fin", null=True, blank=True)
    auto_renew = models.BooleanField("Renouvellement automatique", default=True)
    trial_end = models.DateField("Fin de période d'essai", null=True, blank=True)
    next_billing_date = models.DateField("Prochaine échéance de facturation")
    canceled_at = models.DateField("Date de résiliation", null=True, blank=True)
    cancel_reason = models.TextField(blank=True, default="")
    history = models.JSONField("Historique des changements", default=list, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ("client__name",)

    def __str__(self):
        return f"{self.label} — {self.client.name}"

    @property
    def montant_par_periode_ht(self) -> Decimal:
        price = Decimal(str(self.price_ht or 0))
        discount = Decimal(str(self.discount_percent or 0))
        return (price * (1 - discount / 100)).quantize(Decimal("0.01"))

    @property
    def montant_par_periode_ttc(self) -> Decimal:
        ht = self.montant_par_periode_ht
        tva = Decimal(str(self.vat_rate or 0))
        return (ht * (1 + tva / 100)).quantize(Decimal("0.01"))

    @property
    def mrr_contribution(self) -> Decimal:
        """Contribution MRR selon la périodicité (définition en docs/)."""

        mois = PERIODICITE_MOIS.get(self.periodicity, 1)
        return (self.montant_par_periode_ht / mois).quantize(Decimal("0.01"))

    def date_echeance_suivante(self, depuis: date) -> date:
        mois = PERIODICITE_MOIS.get(self.periodicity, 1)
        year, month = depuis.year, depuis.month + mois
        while month > 12:
            month -= 12
            year += 1
        day = min(depuis.day, 28)
        return date(year, month, day)


class SubscriptionInvoice(CompanyScopedModel):
    """Lien échéance/facture — garantit l'unicité de facturation d'une période
    (anti doublon en cas de relance technique ou de tâche répétée)."""

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="factures_generees")
    invoice = models.OneToOneField(
        "invoicing.Invoice", on_delete=models.PROTECT, related_name="subscription_link"
    )
    period_start = models.DateField()
    period_end = models.DateField()

    class Meta:
        unique_together = ("subscription", "period_start")
