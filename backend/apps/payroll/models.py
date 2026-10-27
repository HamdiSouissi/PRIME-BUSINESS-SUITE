"""Paie française : règles versionnées, cycle de paie, bulletins, DSN.

Aucun taux ni plafond n'est codé en dur dans les fonctions : tout réside dans
`PayrollParameterSet` + `ContributionRule` (données versionnées, sourcées,
datées). Un jeu de règles peut être :
  - brouillon : en cours de saisie ;
  - provisoire : paramètres recueillis depuis des sources officielles mais
    non validés par un expert → la paie peut être SIMULÉE, la validation
    définitive est bloquée ;
  - verifie : contrôlé par une personne compétente (trace obligatoire) ;
  - obsolete : remplacé par une version plus récente.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import CompanyScopedModel, TimeStampedModel


class RulesetStatus(models.TextChoices):
    BROUILLON = "brouillon", "Brouillon"
    PROVISOIRE = "provisoire", "Provisoire (à vérifier)"
    VERIFIE = "verifie", "Vérifié par un expert"
    OBSOLETE = "obsolete", "Obsolète"


class PayrollParameterSet(CompanyScopedModel):
    """Jeu de paramètres sociaux versionné (SMIC, plafonds, clés globales)."""

    label = models.CharField(max_length=128)
    status = models.CharField(
        max_length=16, choices=RulesetStatus.choices, default=RulesetStatus.BROUILLON
    )
    valid_from = models.DateField("En vigueur du")
    valid_to = models.DateField("Au (inclus, facultatif)", null=True, blank=True)

    source_url = models.URLField("Source officielle", blank=True, default="")
    source_label = models.CharField("Référence de la source", max_length=255, blank=True, default="")
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="rulesets_verifies",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_note = models.TextField("Note de vérification", blank=True, default="")

    # Paramètres globaux (valeurs par défaut 2025 — vérifier avant usage réel)
    pmss_mensuel = models.DecimalField(
        "Plafond mensuel de sécurité sociale (€)", max_digits=10, decimal_places=2, default="3925.00"
    )
    pass_annuel = models.DecimalField(
        "Plafond annuel de sécurité sociale (€)", max_digits=10, decimal_places=2, default="47100.00"
    )
    smic_horaire = models.DecimalField(
        "SMIC horaire brut (€)", max_digits=6, decimal_places=2, default="11.88"
    )
    smic_mensuel_35h = models.DecimalField(
        "SMIC mensuel brut 35h (€)", max_digits=10, decimal_places=2, default="1801.80"
    )
    heures_mensuelles_reference = models.DecimalField(
        "Durée mensuelle de référence (h)", max_digits=6, decimal_places=2, default="151.67"
    )
    # Réduction générale dégressive des cotisations patronales
    reduction_generale_active = models.BooleanField("Réduction générale active", default=True)
    reduction_generale_t = models.DecimalField(
        "Coefficient T de la réduction générale", max_digits=6, decimal_places=4, default="0.3194",
        help_text="0,3194 pour les employeurs de moins de 50 salariés (FNAL 0,10).",
    )
    # Assujettissement CSG/CRDS (abattement forfaitaire de 1,75 %)
    csg_assujettissement = models.DecimalField(
        "Part assujettie CSG/CRDS (%)", max_digits=5, decimal_places=2, default="98.25"
    )
    majoration_hs_25 = models.DecimalField("Majoration HS 25 % (jusqu'à 8h)", max_digits=5, decimal_places=2, default="25")
    majoration_hs_50 = models.DecimalField("Majoration HS 50 % (au-delà)", max_digits=5, decimal_places=2, default="50")
    plafond_hs_exonerees = models.DecimalField(
        "Plafond annuel d'exonération salariale des HS (€)", max_digits=10, decimal_places=2, default="7500.00"
    )

    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-valid_from",)

    def __str__(self):
        return f"{self.label} ({self.get_status_display()})"

    @property
    def est_verifie(self):
        return self.status == RulesetStatus.VERIFIE


class ContributionRule(TimeStampedModel):
    """Règle de cotisation individuelle, rattachée à un jeu de paramètres."""

    parameter_set = models.ForeignKey(
        PayrollParameterSet, on_delete=models.CASCADE, related_name="rules"
    )
    code = models.CharField(max_length=32)
    label = models.CharField(max_length=255)
    section = models.CharField(
        max_length=32,
        choices=(
            ("sante", "Santé"),
            ("retraite", "Retraite"),
            ("famille", "Famille"),
            ("chomage", "Assurance chômage"),
            ("at_mp", "Accidents du travail / MP"),
            ("csg_crds", "CSG / CRDS"),
            ("autres", "Autres contributions"),
            ("prevoyance", "Prévoyance / mutuelle"),
        ),
        default="autres",
    )
    BASE_CHOICES = (
        ("brut", "Brut total (déplafonné)"),
        ("tranche_a", "Tranche A (plafonnée au PMSS)"),
        ("tranche_b", "Tranche B (au-delà du PMSS)"),
        ("csg_base", "Base CSG (part assujettie)"),
    )
    base_type = models.CharField(max_length=16, choices=BASE_CHOICES, default="brut")
    ceiling_multiple = models.DecimalField(
        "Plafond multiple du PMSS (0 = sans plafond)", max_digits=4, decimal_places=1, default="1"
    )
    rate_salarial = models.DecimalField("Taux salarial (%)", max_digits=8, decimal_places=4, default=0)
    rate_patronal = models.DecimalField("Taux patronal (%)", max_digits=8, decimal_places=4, default=0)
    cadre_only = models.BooleanField("Cadres uniquement", default=False)
    non_cadre_only = models.BooleanField("Non-cadres uniquement", default=False)
    affects_net_imposable = models.BooleanField(
        "Contribution non déductible ajoutée au net imposable", default=False,
        help_text="Ex. CSG non déductible et CRDS.",
    )
    patronal_part_taxable = models.BooleanField(
        "Part patronale réintégrée au net imposable (prévoyance)", default=False
    )
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "code")

    def __str__(self):
        return f"{self.code} — {self.label}"

    def applies_to(self, is_cadre: bool) -> bool:
        if self.cadre_only and not is_cadre:
            return False
        if self.non_cadre_only and is_cadre:
            return False
        return True


class RunStatus(models.TextChoices):
    PREPARATION = "preparation", "Préparation"
    CONTROLE = "controle", "Contrôle"
    SIMULATION = "simulation", "Simulation"
    ATTENTE_VALIDATION = "attente_validation", "En attente de validation"
    VALIDE = "valide", "Validé"
    CLOTURE = "cloture", "Clôturé"


class PayrollRun(CompanyScopedModel):
    """Cycle de paie mensuel avec étapes contrôlées."""

    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=24, choices=RunStatus.choices, default=RunStatus.PREPARATION)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payroll_runs_lances",
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payroll_runs_valides",
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    history = models.JSONField("Journal des étapes", default=list, blank=True)

    class Meta:
        unique_together = ("company", "year", "month")
        ordering = ("-year", "-month")

    def __str__(self):
        return f"Paie {self.month:02d}/{self.year} — {self.get_status_display()}"

    def log_step(self, user, message: str):
        self.history = self.history + [
            {
                "at": timezone.now().isoformat(),
                "by": user.email if user else "système",
                "message": message,
                "status": self.status,
            }
        ]


class PayslipStatus(models.TextChoices):
    BROUILLON = "brouillon", "Brouillon"
    SIMULE = "simule", "Simulé"
    CONTROLE = "controle", "Contrôlé"
    VALIDE = "valide", "Validé (définitif)"
    EDITE = "edite", "Édité et mis à disposition"
    CLOTURE = "cloture", "Clôturé"


class Payslip(CompanyScopedModel):
    """Bulletin de paie : instantané complet des entrées, règles et résultats."""

    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey("hr.Employee", on_delete=models.PROTECT, related_name="bulletins")
    contract = models.ForeignKey("hr.Contract", on_delete=models.PROTECT, null=True, blank=True)
    parameter_set = models.ForeignKey(
        PayrollParameterSet, on_delete=models.PROTECT, related_name="payslips",
        help_text="Jeu de règles épinglé au moment du calcul.",
    )
    number = models.CharField("Numéro", max_length=32, blank=True, default="")
    status = models.CharField(max_length=16, choices=PayslipStatus.choices, default=PayslipStatus.BROUILLON)

    # Entrées : variables du mois (primes, absences, heures supplémentaires…)
    inputs = models.JSONField("Variables de paie", default=dict, blank=True)
    # Résultat complet (totaux + lignes) — instantané d'audit
    result = models.JSONField("Résultat du calcul", default=dict, blank=True)
    result_hash = models.CharField("Empreinte SHA-256 du résultat", max_length=64, blank=True, default="")

    # Totaux dénormalisés pour les listes et les rapports
    brut = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cotisations_salariales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cotisations_patronales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allegements = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_social = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_imposable = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    prelevement_a_la_source = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_a_payer = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cout_employeur = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    provisional = models.BooleanField(
        "Calcul provisoire (règles non vérifiées)", default=True
    )
    pdf = models.FileField(upload_to="payroll/bulletins/%Y/%m/", null=True, blank=True)
    published_to_employee = models.BooleanField("Mis à disposition du salarié", default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("run", "employee")
        ordering = ("employee__last_name",)

    def __str__(self):
        return f"Bulletin {self.employee} — {self.run.month:02d}/{self.run.year}"


class PayslipLine(TimeStampedModel):
    """Ligne de cotisation calculée, stockée pour l'affichage et l'audit."""

    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="lines")
    section = models.CharField(max_length=32, default="autres")
    code = models.CharField(max_length=32)
    label = models.CharField(max_length=255)
    base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rate_salarial = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    amount_salarial = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rate_patronal = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    amount_patronal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_allegement = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)


class DSNExport(CompanyScopedModel):
    """Préparation / transmission DSN.

    ATTENTION : le fichier généré ici est une PRÉPARATION interne des données
    DSN. Il n'est ni transmis ni certifié : l'intégration avec net-entreprises
    ou un prestataire homologué reste à réaliser (voir documentation).
    Les champs de statut et de preuve sont prévus pour cette intégration.
    """

    STATUTS = (
        ("prepare", "Préparé (non transmis)"),
        ("transmis", "Transmis"),
        ("accepte", "Accepté (retour reçu)"),
        ("rejete", "Rejeté (retour reçu)"),
    )

    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="dsn_exports")
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    file = models.FileField(upload_to="payroll/dsn/%Y/%m/", null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUTS, default="prepare")
    submitted_at = models.DateTimeField("Date de transmission réelle", null=True, blank=True)
    receipt_reference = models.CharField(
        "Référence du récépissé officiel", max_length=128, blank=True, default=""
    )
    feedback = models.JSONField("Retours du dispositif", default=dict, blank=True)
    notes = models.TextField(blank=True, default="")
