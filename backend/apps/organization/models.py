"""Configuration de l'entreprise (section 3 du cahier des charges).

Toutes les règles métier de la suite dépendent de la situation réelle de
l'entreprise décrite ici : forme juridique, régime de TVA, effectif,
convention collective… Rien n'est supposé.
"""

from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import TimeStampedModel


class Company(TimeStampedModel):
    FORMES_JURIDIQUES = (
        ("sasu", "SASU"),
        ("sas", "SAS"),
        ("eurl", "EURL"),
        ("sarl", "SARL"),
        ("sa", "SA"),
        ("snc", "SNC"),
        ("sci", "SCI"),
        ("ei", "Entreprise individuelle"),
        ("autre", "Autre"),
    )

    REGIMES_TVA = (
        ("reel_normal", "Réel normal"),
        ("reel_simplifie", "Réel simplifié"),
        ("franchise", "Franchise en base de TVA"),
        ("non_assujetti", "Non assujetti"),
    )

    name = models.CharField("Raison sociale", max_length=255)
    legal_form = models.CharField("Forme juridique", max_length=16, choices=FORMES_JURIDIQUES)
    address = models.TextField("Adresse", blank=True, default="")
    postal_code = models.CharField("Code postal", max_length=10, blank=True, default="")
    city = models.CharField("Ville", max_length=128, blank=True, default="")
    country = models.CharField("Pays", max_length=64, default="France")
    email = models.EmailField("E-mail", blank=True, default="")
    phone = models.CharField("Téléphone", max_length=32, blank=True, default="")
    website = models.URLField("Site web", blank=True, default="")

    siren = models.CharField(
        "SIREN", max_length=9, blank=True, default="",
        validators=[RegexValidator(r"^\d{9}$", "9 chiffres attendus")],
    )
    siret = models.CharField(
        "SIRET", max_length=14, blank=True, default="",
        validators=[RegexValidator(r"^\d{14}$", "14 chiffres attendus")],
    )
    vat_number = models.CharField("N° TVA intracommunautaire", max_length=32, blank=True, default="")
    rcs_city = models.CharField("RCS (ville)", max_length=64, blank=True, default="")
    rcs_number = models.CharField("N° RCS", max_length=32, blank=True, default="")
    naf_code = models.CharField("Code APE/NAF", max_length=8, blank=True, default="")

    share_capital = models.DecimalField(
        "Capital social (€)", max_digits=14, decimal_places=2, default=0
    )
    currency = models.CharField("Devise principale", max_length=3, default="EUR")
    vat_regime = models.CharField(
        "Régime de TVA", max_length=20, choices=REGIMES_TVA, default="reel_normal"
    )
    fiscal_year_start_month = models.PositiveSmallIntegerField(
        "Mois de début d'exercice (1-12)", default=1
    )

    # Coordonnées bancaires principales de l'entreprise
    bank_iban = models.CharField("IBAN", max_length=34, blank=True, default="")
    bank_bic = models.CharField("BIC", max_length=11, blank=True, default="")
    bank_name = models.CharField("Banque", max_length=128, blank=True, default="")

    # Identité visuelle
    logo = models.ImageField(upload_to="logos/", blank=True, null=True)

    # Paramètres régionaux / sociaux
    collective_agreement = models.CharField(
        "Convention collective applicable", max_length=255, blank=True, default="",
        help_text="Ex. Syntec, commerce de gros…",
    )
    collective_agreement_idcc = models.CharField("IDCC", max_length=8, blank=True, default="")
    work_time_weekly_hours = models.DecimalField(
        "Durée hebdomadaire collective (h)", max_digits=4, decimal_places=2, default=35
    )

    # Expert-comptable
    accountant_name = models.CharField("Expert-comptable", max_length=255, blank=True, default="")
    accountant_email = models.EmailField(blank=True, default="")
    accountant_phone = models.CharField(max_length=32, blank=True, default="")

    # Effectif (pilote certaines obligations de conformité)
    headcount = models.PositiveIntegerField("Effectif", default=0)

    # Mention complémentaire de facturation (mentions obligatoires…)
    invoice_footer = models.TextField("Pied de page des documents", blank=True, default="")

    def __str__(self):
        return self.name

    @property
    def is_franchise_tva(self) -> bool:
        return self.vat_regime == "franchise"
