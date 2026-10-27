"""Facturation clients et fournisseurs (sections 8 et 9 du cahier des charges)."""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import CompanyScopedModel, TimeStampedModel


class Client(CompanyScopedModel):
    name = models.CharField("Raison sociale / nom", max_length=255)
    code = models.CharField("Code client", max_length=32)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    address = models.TextField(blank=True, default="")
    siret = models.CharField(max_length=14, blank=True, default="")
    vat_number = models.CharField("N° TVA du client", max_length=32, blank=True, default="")
    payment_terms_days = models.PositiveSmallIntegerField("Délai de paiement (jours)", default=30)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        unique_together = ("company", "code")
        ordering = ("name",)

    def __str__(self):
        return self.name


class Supplier(CompanyScopedModel):
    name = models.CharField("Raison sociale / nom", max_length=255)
    code = models.CharField("Code fournisseur", max_length=32)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    address = models.TextField(blank=True, default="")
    siret = models.CharField(max_length=14, blank=True, default="")
    vat_number = models.CharField(max_length=32, blank=True, default="")
    default_expense_account = models.CharField(
        "Compte de charge par défaut", max_length=16, blank=True, default=""
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "code")
        ordering = ("name",)

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Devis
# ---------------------------------------------------------------------------

class QuoteStatus(models.TextChoices):
    BROUILLON = "brouillon", "Brouillon"
    ENVOYE = "envoye", "Envoyé"
    ACCEPTE = "accepte", "Accepté"
    REFUSE = "refuse", "Refusé"
    EXPIRE = "expire", "Expiré"


class Quote(CompanyScopedModel):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="devis")
    number = models.CharField("Numéro", max_length=32, blank=True, default="")
    status = models.CharField(max_length=16, choices=QuoteStatus.choices, default=QuoteStatus.BROUILLON)
    issue_date = models.DateField("Date d'émission", default=timezone.localdate)
    validity_days = models.PositiveSmallIntegerField("Validité (jours)", default=30)
    subject = models.CharField("Objet", max_length=255, blank=True, default="")
    total_ht = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_vat = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-issue_date",)


class QuoteLine(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="lines")
    order = models.PositiveSmallIntegerField(default=0)
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price_ht = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vat_rate = models.DecimalField("Taux de TVA (%)", max_digits=5, decimal_places=2, default="20")


# ---------------------------------------------------------------------------
# Factures clients
# ---------------------------------------------------------------------------

class InvoiceType(models.TextChoices):
    FACTURE = "facture", "Facture"
    AVOIR = "avoir", "Avoir"
    ACOMPTE = "acompte", "Facture d'acompte"


class InvoiceStatus(models.TextChoices):
    BROUILLON = "brouillon", "Brouillon"
    EMISE = "emise", "Émise"
    PARTIELLEMENT_PAYEE = "partielle", "Partiellement payée"
    PAYEE = "payee", "Payée"
    EN_RETARD = "en_retard", "En retard"
    ANNULEE = "annulee", "Annulée (par avoir)"


class EInvoiceStatus(models.TextChoices):
    NON_APPLICABLE = "na", "Non applicable"
    A_TRANSMETTRE = "a_transmettre", "À transmettre"
    TRANSMISE = "transmise", "Transmise (preuve conservée)"
    REJETEE = "rejetee", "Rejetée par la plateforme"


class Invoice(CompanyScopedModel):
    """Facture client émise. Une facture ÉMISE n'est jamais supprimée :
    correction par avoir ou par écriture de régularisation."""

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="factures")
    number = models.CharField("Numéro", max_length=32, blank=True, default="", db_index=True)
    invoice_type = models.CharField(max_length=12, choices=InvoiceType.choices, default=InvoiceType.FACTURE)
    status = models.CharField(max_length=16, choices=InvoiceStatus.choices, default=InvoiceStatus.BROUILLON)
    issue_date = models.DateField("Date d'émission")
    due_date = models.DateField("Date d'échéance")
    credit_note_of = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="avoirs",
        verbose_name="Facture annulée (si avoir)",
    )
    currency = models.CharField(max_length=3, default="EUR")
    total_ht = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_vat = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Facturation électronique (réforme française) — préparation
    einvoice_status = models.CharField(
        "Statut de transmission électronique", max_length=16,
        choices=EInvoiceStatus.choices, default=EInvoiceStatus.NON_APPLICABLE,
    )
    einvoice_platform_id = models.CharField(
        "Identifiant plateforme (PDP/partenaire)", max_length=128, blank=True, default=""
    )
    einvoice_proof = models.JSONField("Preuves techniques de transmission", default=dict, blank=True)

    pdf = models.FileField(upload_to="invoices/%Y/%m/", null=True, blank=True)
    accounting_entry = models.ForeignKey(
        "accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="Écriture comptable",
    )
    source = models.CharField("Origine", max_length=64, default="manuel")
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-issue_date", "-id")
        indexes = [models.Index(fields=["company", "status", "due_date"])]

    def __str__(self):
        return f"{self.number or 'Brouillon'} — {self.client.name}"

    @property
    def reste_a_payer(self) -> Decimal:
        return (self.total_ttc or 0) - (self.amount_paid or 0)


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    order = models.PositiveSmallIntegerField(default=0)
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price_ht = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vat_rate = models.DecimalField("Taux de TVA (%)", max_digits=5, decimal_places=2, default="20")
    total_ht = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_vat = models.DecimalField(max_digits=14, decimal_places=2, default=0)


class PaymentSchedule(CompanyScopedModel):
    """Échéancier de règlement d'une facture ou d'un abonnement."""

    invoice = models.ForeignKey(
        Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="echeancier"
    )
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    label = models.CharField(max_length=255, blank=True, default="")
    is_paid = models.BooleanField(default=False)

    class Meta:
        ordering = ("due_date",)


# ---------------------------------------------------------------------------
# Factures fournisseurs
# ---------------------------------------------------------------------------

class SupplierInvoiceStatus(models.TextChoices):
    RECUE = "recue", "Reçue"
    A_VALIDER = "a_valider", "À valider"
    VALIDEE = "validee", "Validée (comptabilisée)"
    PARTIELLEMENT_PAYEE = "partielle", "Partiellement payée"
    PAYEE = "payee", "Payée"
    EN_RETARD = "en_retard", "En retard"
    LITIGE = "litige", "En litige"


class SupplierInvoice(CompanyScopedModel):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="factures")
    internal_number = models.CharField("N° interne", max_length=32, blank=True, default="")
    supplier_reference = models.CharField("Référence fournisseur", max_length=64, blank=True, default="")
    status = models.CharField(max_length=16, choices=SupplierInvoiceStatus.choices, default=SupplierInvoiceStatus.RECUE)
    received_date = models.DateField("Date de réception", default=timezone.localdate)
    invoice_date = models.DateField("Date de facture")
    due_date = models.DateField("Date d'échéance")
    total_ht = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_vat = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expense_account = models.CharField(
        "Compte de charge", max_length=16, blank=True, default="",
        help_text="Par défaut : compte du fournisseur, sinon 603000.",
    )
    file = models.FileField(upload_to="invoices/suppliers/%Y/%m/", null=True, blank=True)
    accounting_entry = models.ForeignKey(
        "accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ("-invoice_date",)

    @property
    def reste_a_payer(self) -> Decimal:
        return (self.total_ttc or 0) - (self.amount_paid or 0)


class SupplierInvoiceLine(models.Model):
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE, related_name="lines")
    order = models.PositiveSmallIntegerField(default=0)
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price_ht = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default="20")
    total_ht = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_vat = models.DecimalField(max_digits=14, decimal_places=2, default=0)


# ---------------------------------------------------------------------------
# Règlements, relances
# ---------------------------------------------------------------------------

class PaymentMethod(models.TextChoices):
    VIREMENT = "virement", "Virement"
    CARTE = "carte", "Carte bancaire"
    CHEQUE = "cheque", "Chèque"
    ESPECES = "especes", "Espèces"
    PRELEVEMENT = "prelevement", "Prélèvement"
    AUTRE = "autre", "Autre"


class Payment(CompanyScopedModel):
    """Règlement constaté (encaissement client ou décaissement fournisseur).

    Un enregistrement correspond à un règlement RÉEL (rapproché ensuite avec
    les opérations bancaires). L' exécution d'un virement ÉMIS reste hors
    application (validation humaine + banque) — cf. section 7.
    """

    DIRECTIONS = (("recu", "Encaissement"), ("emis", "Décaissement"))

    invoice = models.ForeignKey(
        Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="paiements"
    )
    supplier_invoice = models.ForeignKey(
        SupplierInvoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="paiements"
    )
    direction = models.CharField(max_length=8, choices=DIRECTIONS, default="recu")
    date = models.DateField(default=timezone.localdate)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=16, choices=PaymentMethod.choices, default=PaymentMethod.VIREMENT)
    reference = models.CharField(max_length=128, blank=True, default="")
    bank_transaction = models.ForeignKey(
        "treasury.BankTransaction", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ("-date",)


class ReminderLog(CompanyScopedModel):
    """Relance de facture client (traçabilité du recouvrement)."""

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="relances")
    level = models.PositiveSmallIntegerField("Niveau (1, 2, 3)")
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    channel = models.CharField(max_length=16, default="email")
    note = models.TextField(blank=True, default="")

    class Meta:
        unique_together = ("invoice", "level")
        ordering = ("sent_at",)


# ---------------------------------------------------------------------------
# Configuration facturation électronique (préparation réforme 2026-2027)
# ---------------------------------------------------------------------------

class EInvoicingConfig(CompanyScopedModel):
    """Configuration du partenaire de facturation électronique.

    L'application est PRÉPARÉE à la réforme (statuts, archivage des preuves,
    point d'intégration) mais n'est pas déclarée « conforme » : l'intégration
    avec une plateforme agréée doit être réalisée et testée (voir docs).
    """

    provider_name = models.CharField("Plateforme partenaire", max_length=128, blank=True, default="")
    provider_base_url = models.URLField("URL de l'API partenaire", blank=True, default="")
    api_key_encrypted = models.TextField("Clé API (chiffrée)", blank=True, default="")
    environment = models.CharField(
        max_length=16,
        choices=(("test", "Test / qualification"), ("production", "Production")),
        default="test",
    )
    transmission_enabled = models.BooleanField("Transmission active", default=False)
    reception_enabled = models.BooleanField("Réception active", default=False)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
