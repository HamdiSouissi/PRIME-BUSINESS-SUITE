"""Associés, capital, comptes courants et dividendes (section 12)."""

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import CompanyScopedModel


class Associate(CompanyScopedModel):
    """Associé de la société et participation au capital."""

    civility = models.CharField(max_length=8, blank=True, default="")
    first_name = models.CharField(max_length=128)
    last_name = models.CharField(max_length=128)
    email = models.EmailField(blank=True, default="")
    is_company = models.BooleanField("Personne morale", default=False)
    company_name = models.CharField(max_length=255, blank=True, default="")
    shares = models.PositiveBigIntegerField("Nombre de parts")
    entry_date = models.DateField("Date d'entrée au capital")
    exit_date = models.DateField("Date de sortie", null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-shares", "last_name")

    def __str__(self):
        if self.is_company:
            return self.company_name
        return f"{self.first_name} {self.last_name}"

    @property
    def pct_capital(self) -> Decimal:
        total = self.company_capital_parts_total
        if not total:
            return Decimal(0)
        return (Decimal(self.shares) / Decimal(total) * 100).quantize(Decimal("0.01"))

    @property
    def company_capital_parts_total(self):
        from django.db.models import Sum

        return (
            Associate.objects.filter(company=self.company, exit_date__isnull=True)
            .aggregate(total=Sum("shares"))["total"]
            or 0
        )


class CapitalMovement(CompanyScopedModel):
    """Historique des apports / variations de capital."""

    TYPES = (
        ("apport_initial", "Apport initial"),
        ("augmentation", "Augmentation de capital"),
        ("reduction", "Réduction de capital"),
        ("cession", "Cession de parts"),
    )

    date = models.DateField()
    movement_type = models.CharField(max_length=20, choices=TYPES)
    associate = models.ForeignKey(Associate, on_delete=models.PROTECT, related_name="mouvements")
    shares_delta = models.IntegerField("Variation (+/-) de parts")
    amount = models.DecimalField("Montant (€)", max_digits=14, decimal_places=2, default=0)
    document = models.FileField("Justificatif / PV", upload_to="capital/%Y/", null=True, blank=True)
    note = models.TextField(blank=True, default="")


class CurrentAccountEntry(CompanyScopedModel):
    """Compte courant d'associé : apports et retraits."""

    TYPES = (("apport", "Apport en compte courant"), ("retrait", "Retrait"), ("interet", "Intérêts"))

    associate = models.ForeignKey(Associate, on_delete=models.CASCADE, related_name="compte_courant")
    date = models.DateField()
    entry_type = models.CharField(max_length=16, choices=TYPES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    label = models.CharField(max_length=255, blank=True, default="")
    accounting_entry = models.ForeignKey(
        "accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ("date",)


class DistributionStatus(models.TextChoices):
    PROJET = "projet", "Projet (non décidé)"
    DECIDEE = "decidee", "Décidée en assemblée"
    PAYEE = "payee", "Payée"
    ANNULEE = "annulee", "Annulée"


class DistributionDecision(CompanyScopedModel):
    """Décision de distribution : conditions légales vérifiées AVANT décision.

    - Le montant « distribuable » n'est JAMAIS le solde bancaire : c'est le
      résultat distribuable calculé depuis le résultat de l'exercice ET les
      réserves légales (5 % du bénéfice jusqu'à 10 % du capital pour SARL/SAS…).
    - La décision et son document d'assemblée sont obligatoires avant tout
      paiement (garde-fous dans les services).
    """

    fiscal_year = models.PositiveIntegerField("Exercice concerné")
    meeting_date = models.DateField("Date d'assemblée")
    status = models.CharField(max_length=16, choices=DistributionStatus.choices, default=DistributionStatus.PROJET)
    resultat_exercice = models.DecimalField("Résultat de l'exercice (€)", max_digits=14, decimal_places=2)
    report_a_nouveau = models.DecimalField("Report à nouveau (€)", max_digits=14, decimal_places=2, default=0)
    autres_reserves = models.DecimalField("Autres réserves distribuables (€)", max_digits=14, decimal_places=2, default=0)
    somme_distribuable = models.DecimalField("Somme distribuable vérifiée (€)", max_digits=14, decimal_places=2, default=0)
    montant_decide = models.DecimalField("Montant décidé (€)", max_digits=14, decimal_places=2, default=0)
    # Paramètre fiscal par défaut : PFU (flat tax) 30 % pour les personnes physiques
    withholding_rate = models.DecimalField("Taux de retenue (%, PFU par défaut)", max_digits=5, decimal_places=2, default="30")
    decision_document = models.FileField("PV d'assemblée", upload_to="dividendes/%Y/", null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-fiscal_year",)

    def __str__(self):
        return f"Distribution {self.fiscal_year} — {self.get_status_display()}"


class DividendPayment(CompanyScopedModel):
    """Paiement de dividendes à un associé (trace du net et de la retenue)."""

    decision = models.ForeignKey(DistributionDecision, on_delete=models.CASCADE, related_name="paiements")
    associate = models.ForeignKey(Associate, on_delete=models.PROTECT, related_name="dividendes")
    gross_amount = models.DecimalField("Montant brut (€)", max_digits=14, decimal_places=2)
    withholding_amount = models.DecimalField("Retenue à la source (€)", max_digits=14, decimal_places=2, default=0)
    net_amount = models.DecimalField("Net versé (€)", max_digits=14, decimal_places=2)
    paid_on = models.DateField(null=True, blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    proof = models.FileField("Justificatif de paiement", upload_to="dividendes/%Y/", null=True, blank=True)

    class Meta:
        unique_together = ("decision", "associate")
