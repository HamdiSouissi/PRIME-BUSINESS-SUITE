"""Comptabilité générale en partie double (section 6 du cahier des charges).

Invariants garantis côté serveur :
- toute écriture est équilibrée (∑ débit = ∑ crédit) avant validation ;
- une écriture validée n'est ni modifiée ni supprimée (correction par
  contre-passation uniquement) ;
- une année clôturée/verrouillée n'accepte plus d'écriture ;
- chaque écriture porte une origine (source) et un auteur.
"""

from django.conf import settings
from django.db import models

from apps.core.models import CompanyScopedModel


class Account(CompanyScopedModel):
    """Compte du plan comptable (adaptable au référentiel de l'entreprise)."""

    TYPES = (
        ("general", "Compte général"),
        ("client", "Compte auxiliaire client"),
        ("fournisseur", "Compte auxiliaire fournisseur"),
        ("banque", "Compte bancaire"),
        ("caisse", "Caisse"),
    )

    number = models.CharField("Numéro", max_length=16)
    label = models.CharField("Intitulé", max_length=255)
    account_class = models.CharField("Classe (PCG)", max_length=2)
    account_type = models.CharField("Type", max_length=16, choices=TYPES, default="general")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "number")
        ordering = ("number",)

    def __str__(self):
        return f"{self.number} — {self.label}"


class Journal(CompanyScopedModel):
    TYPES = (
        ("ventes", "Journal des ventes"),
        ("achats", "Journal des achats"),
        ("banque", "Journal de banque"),
        ("paie", "Journal de paie"),
        ("od", "Opérations diverses"),
    )

    code = models.CharField(max_length=8)
    label = models.CharField(max_length=128)
    journal_type = models.CharField(max_length=12, choices=TYPES, default="od")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "code")

    def __str__(self):
        return f"{self.code} — {self.label}"


class FiscalYear(CompanyScopedModel):
    """Exercice comptable. `locked`/`closed` bloquent les écritures."""

    STATUTS = (
        ("ouvert", "Ouvert"),
        ("verrouille", "Verrouillé (préparation clôture)"),
        ("cloture", "Clôturé"),
    )

    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=16, choices=STATUTS, default="ouvert")

    class Meta:
        ordering = ("-start_date",)

    def __str__(self):
        return f"{self.company.name} — exercice {self.start_date.year}"

    @classmethod
    def pour_date(cls, company, date_valeur):
        return cls.objects.filter(
            company=company, start_date__lte=date_valeur, end_date__gte=date_valeur
        ).first()


class EntryStatus(models.TextChoices):
    BROUILLON = "brouillon", "Brouillon"
    VALIDEE = "validee", "Validée (non modifiable)"
    CONTRE_PASSEE = "contre_passee", "Contre-passée"


class JournalEntry(CompanyScopedModel):
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT)
    date = models.DateField()
    reference = models.CharField("Référence", max_length=32, blank=True, default="", db_index=True)
    label = models.CharField("Libellé", max_length=255)
    status = models.CharField(max_length=16, choices=EntryStatus.choices, default=EntryStatus.BROUILLON)
    # Origine de l'écriture (piste d'audit)
    source_model = models.CharField(max_length=64, blank=True, default="")
    source_id = models.CharField(max_length=64, blank=True, default="")
    source_label = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ecritures_creees",
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ecritures_validees",
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    reverses = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="contre_passations"
    )

    class Meta:
        ordering = ("-date", "-id")

    def __str__(self):
        return f"{self.reference} — {self.label}"

    @property
    def total_debit(self):
        return sum(line.debit for line in self.lines.all())

    @property
    def total_credit(self):
        return sum(line.credit for line in self.lines.all())


class EntryLine(models.Model):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    label = models.CharField(max_length=255, blank=True, default="")
    auxiliary = models.CharField(
        "Auxiliaire (client/fournisseur)", max_length=255, blank=True, default=""
    )
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ("id",)
