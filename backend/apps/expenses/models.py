"""Notes de frais (section 11 du cahier des charges)."""

from django.conf import settings
from django.db import models

from apps.core.models import CompanyScopedModel


class ExpenseReportStatus(models.TextChoices):
    BROUILLON = "brouillon", "Brouillon"
    SOUMISE = "soumise", "Soumise"
    VALIDEE = "validee", "Validée (remboursable)"
    REFUSEE = "refusee", "Refusée"
    REMBOURSEE = "remboursee", "Remboursée"
    COMPTABILISEE = "comptabilisee", "Comptabilisée"


class ExpenseCategory(CompanyScopedModel):
    code = models.CharField(max_length=32)
    label = models.CharField(max_length=128)
    # Plafond de la politique de remboursement (0 = pas de plafond)
    max_amount = models.DecimalField("Plafond par ligne (€, 0 = illimité)", max_digits=10, decimal_places=2, default=0)
    receipt_required = models.BooleanField("Justificatif obligatoire", default=True)
    vat_recoverable = models.BooleanField("TVA récupérable", default=True)
    expense_account = models.CharField("Compte de charge", max_length=16, blank=True, default="625100")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "code")

    def __str__(self):
        return self.label


class ExpenseReport(CompanyScopedModel):
    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="notes_de_frais")
    title = models.CharField("Objet", max_length=255)
    status = models.CharField(max_length=16, choices=ExpenseReportStatus.choices, default=ExpenseReportStatus.BROUILLON)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_comment = models.TextField(blank=True, default="")
    reimbursed_at = models.DateField(null=True, blank=True)
    accounting_entry = models.ForeignKey(
        "accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.title} — {self.employee}"


class ExpenseLine(CompanyScopedModel):
    report = models.ForeignKey(ExpenseReport, on_delete=models.CASCADE, related_name="lines")
    date = models.DateField()
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT)
    merchant = models.CharField("Commerçant", max_length=255, blank=True, default="")
    description = models.CharField(max_length=500, blank=True, default="")
    amount_ttc = models.DecimalField("Montant TTC (€)", max_digits=12, decimal_places=2)
    vat_amount = models.DecimalField("TVA (€)", max_digits=12, decimal_places=2, default=0)
    receipt = models.FileField("Justificatif", upload_to="expenses/%Y/%m/", null=True, blank=True)
    project = models.CharField("Projet / client affecté", max_length=128, blank=True, default="")
    over_policy = models.BooleanField("Hors politique de remboursement", default=False)
    duplicate_suspect = models.BooleanField("Doublon suspecté", default=False)

    class Meta:
        ordering = ("date",)
