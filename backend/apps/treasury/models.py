"""Trésorerie : comptes bancaires, opérations, rapprochement (section 7)."""

import hashlib

from django.conf import settings
from django.db import models

from apps.core.models import CompanyScopedModel


class BankAccount(CompanyScopedModel):
    label = models.CharField("Libellé du compte", max_length=128)
    bank_name = models.CharField("Banque", max_length=128, blank=True, default="")
    iban = models.CharField("IBAN", max_length=34, blank=True, default="")
    bic = models.CharField("BIC", max_length=11, blank=True, default="")
    currency = models.CharField(max_length=3, default="EUR")
    is_main = models.BooleanField("Compte principal", default=False)
    initial_balance = models.DecimalField(
        "Solde bancaire initial (à l'ouverture du suivi)", max_digits=14, decimal_places=2, default=0
    )
    initial_balance_date = models.DateField("Date du solde initial", null=True, blank=True)
    accounting_account = models.CharField(
        "Compte comptable associé (512…)", max_length=16, default="512000"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-is_main", "label")

    def __str__(self):
        return f"{self.label} ({self.bank_name})"


class BankTransaction(CompanyScopedModel):
    """Opération bancaire importée (relevé) ou saisie.

    `dedupe_hash` : empreinte (compte, date, libellé, montant) empêchant tout
    doublon d'import.
    """

    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="operations")
    date = models.DateField()
    value_date = models.DateField(null=True, blank=True)
    label = models.CharField(max_length=500)
    amount = models.DecimalField("Montant signé (€)", max_digits=14, decimal_places=2)
    method = models.CharField(max_length=32, blank=True, default="")
    reference = models.CharField(max_length=128, blank=True, default="")
    dedupe_hash = models.CharField(max_length=64, db_index=True)

    # Rapprochement
    reconciled = models.BooleanField("Rapprochée", default=False)
    payment = models.ForeignKey(
        "invoicing.Payment", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    reconciled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("bank_account", "dedupe_hash")
        ordering = ("-date", "-id")
        indexes = [models.Index(fields=["company", "date"])]

    @staticmethod
    def compute_hash(bank_account_id, date_valeur, label, amount) -> str:
        raw = f"{bank_account_id}|{date_valeur}|{label.strip()}|{amount}"
        return hashlib.sha256(raw.encode()).hexdigest()


class CashEvent(CompanyScopedModel):
    """Événement de trésorerie planifié manuellement (hors flux automatiques)."""

    DIRECTIONS = (("in", "Entrée prévue"), ("out", "Sortie prévue"))

    label = models.CharField(max_length=255)
    direction = models.CharField(max_length=8, choices=DIRECTIONS)
    expected_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    category = models.CharField(max_length=64, blank=True, default="manuel")
    is_recurring_monthly = models.BooleanField("Récurrent (mensuel)", default=False)
    probability = models.DecimalField(
        "Probabilité de réalisation (0-1)", max_digits=3, decimal_places=2, default=1
    )
    is_realized = models.BooleanField(default=False)

    class Meta:
        ordering = ("expected_date",)
