"""Ressources humaines : salariés, contrats, absences, matériel, documents."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import CompanyScopedModel, TimeStampedModel


class Employee(CompanyScopedModel):
    """Dossier complet d'un salarié."""

    STATUTS = (
        ("actif", "Actif"),
        ("arrivee_prevue", "Arrivée prévue"),
        ("sorti", "Sorti"),
    )

    matricule = models.CharField("Matricule", max_length=32)
    civility = models.CharField("Civilité", max_length=8, blank=True, default="")
    first_name = models.CharField("Prénom", max_length=128)
    last_name = models.CharField("Nom", max_length=128)
    birth_date = models.DateField("Date de naissance", null=True, blank=True)
    birth_city = models.CharField("Ville de naissance", blank=True, max_length=128, default="")
    nationality = models.CharField("Nationalité", max_length=64, default="Française")
    social_security_number = models.CharField(
        "N° de sécurité sociale", max_length=15, blank=True, default=""
    )

    email_pro = models.EmailField("E-mail professionnel", blank=True, default="")
    email_perso = models.EmailField("E-mail personnel", blank=True, default="")
    phone = models.CharField("Téléphone", max_length=32, blank=True, default="")
    address = models.TextField("Adresse", blank=True, default="")

    # Coordonnées bancaires — accès restreint (voir permissions RH/PAIE).
    bank_iban = models.CharField("IBAN", max_length=34, blank=True, default="")
    bank_bic = models.CharField("BIC", max_length=11, blank=True, default="")

    position = models.CharField("Poste", max_length=128, blank=True, default="")
    department = models.CharField("Service", max_length=128, blank=True, default="")
    manager = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="subordonnees", verbose_name="Responsable",
    )
    hire_date = models.DateField("Date d'embauche")
    status = models.CharField("Statut", max_length=20, choices=STATUTS, default="actif")
    exit_date = models.DateField("Date de sortie", null=True, blank=True)

    # Compte utilisateur lié (accès au portail salarié), facultatif.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="employee_profile",
    )

    # Compteurs d'heures mensuels familiers (affichage bulletin)
    emergency_contact = models.CharField("Contact d'urgence", max_length=255, blank=True, default="")

    class Meta:
        unique_together = ("company", "matricule")
        ordering = ("last_name", "first_name")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def contrat_actif(self):
        today = self.hire_date  # valeur par défaut
        from django.utils import timezone

        today = timezone.localdate()
        return (
            self.contrats.filter(start_date__lte=today)
            .filter(models.Q(end_date__isnull=True) | models.Q(end_date__gte=today))
            .order_by("-start_date")
            .first()
        )


class Contract(TimeStampedModel):
    """Contrat de travail (historisé via `ContractAmendment`)."""

    TYPES = (
        ("cdi", "CDI"),
        ("cdd", "CDD"),
        ("alternance", "Alternance / apprentissage"),
        ("stage", "Stage"),
        ("freelance", "Prestation indépendante"),
        ("autre", "Autre"),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="contrats")
    contract_type = models.CharField("Type de contrat", max_length=16, choices=TYPES)
    start_date = models.DateField("Date de début")
    end_date = models.DateField("Date de fin", null=True, blank=True)

    weekly_hours = models.DecimalField("Heures hebdomadaires", max_digits=4, decimal_places=2, default=35)
    gross_monthly_salary = models.DecimalField(
        "Salaire brut mensuel (€)", max_digits=12, decimal_places=2
    )
    is_cadre = models.BooleanField("Statut cadre", default=False)
    classification = models.CharField(
        "Classification / coefficient", max_length=64, blank=True, default=""
    )
    position_level = models.CharField("Niveau (convention collective)", max_length=64, blank=True, default="")
    collective_agreement = models.CharField(
        "Convention collective (si spécifique)", max_length=255, blank=True, default=""
    )

    # Période d'essai
    trial_end_date = models.DateField("Fin de période d'essai", null=True, blank=True)
    trial_renewed = models.BooleanField("Essai renouvelé", default=False)

    # Prélèvement à la source — taux transmis par l'administration (confidentiel)
    withholding_rate = models.DecimalField(
        "Taux de prélèvement à la source (%)", max_digits=5, decimal_places=2, default=0
    )

    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-start_date",)

    def __str__(self):
        return f"{self.employee} — {self.get_contract_type_display()} ({self.start_date})"

    def clean(self):
        if self.contract_type in {"cdd", "alternance", "stage"} and not self.end_date:
            raise ValidationError(
                {"end_date": "Une date de fin est obligatoire pour ce type de contrat."}
            )
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "La fin ne peut pas précéder le début."})


class ContractAmendment(TimeStampedModel):
    """Avenant / modification contractuelle tracée."""

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="avenants")
    effective_date = models.DateField("Date d'effet")
    reason = models.CharField("Motif", max_length=255)
    changes = models.JSONField("Champs modifiés (avant/après)", default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )


class LeaveType(CompanyScopedModel):
    code = models.CharField(max_length=16)
    label = models.CharField(max_length=128)
    is_paid = models.BooleanField("Congé payé", default=True)
    annual_days = models.DecimalField("Jours acquis par an", max_digits=5, decimal_places=1, default=25)
    color = models.CharField(max_length=7, blank=True, default="#2563eb")

    class Meta:
        unique_together = ("company", "code")

    def __str__(self):
        return self.label


class LeaveRequest(CompanyScopedModel):
    STATUTS = (
        ("brouillon", "Brouillon"),
        ("soumise", "En attente de validation"),
        ("validee", "Validée"),
        ("refusee", "Refusée"),
        ("annulee", "Annulée"),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="absences")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    half_day_start = models.BooleanField("Début à la mi-journée", default=False)
    half_day_end = models.BooleanField("Fin à la mi-journée", default=False)
    business_days = models.DecimalField("Jours ouvrés", max_digits=5, decimal_places=1)
    status = models.CharField(max_length=16, choices=STATUTS, default="soumise")
    comment = models.TextField("Commentaire du salarié", blank=True, default="")
    manager_comment = models.TextField("Commentaire du responsable", blank=True, default="")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-start_date",)

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "La fin ne peut pas précéder le début."})


class LeaveBalance(CompanyScopedModel):
    """Solde de congés par salarié / type / année."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="soldes_conges")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.PositiveIntegerField()
    acquired = models.DecimalField("Acquis", max_digits=6, decimal_places=1, default=0)
    taken = models.DecimalField("Pris", max_digits=6, decimal_places=1, default=0)

    class Meta:
        unique_together = ("employee", "leave_type", "year")

    @property
    def remaining(self):
        return self.acquired - self.taken


class EquipmentItem(CompanyScopedModel):
    """Matériel confié au salarié."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="materiels")
    label = models.CharField(max_length=255)
    serial_number = models.CharField(max_length=128, blank=True, default="")
    given_on = models.DateField()
    returned_on = models.DateField(null=True, blank=True)

    @property
    def is_returned(self):
        return self.returned_on is not None


class TrainingRecord(CompanyScopedModel):
    """Formation suivie."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="formations")
    label = models.CharField(max_length=255)
    provider = models.CharField(max_length=255, blank=True, default="")
    start_date = models.DateField()
    hours = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    certificate_obtained = models.BooleanField(default=False)


class Interview(CompanyScopedModel):
    """Entretien (annuel, professionnel, fin de période d'essai…)."""

    TYPES = (
        ("annuel", "Entretien annuel"),
        ("professionnel", "Entretien professionnel"),
        ("essai", "Fin de période d'essai"),
        ("retour", "Retour de longue absence"),
        ("autre", "Autre"),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="entretiens")
    interview_type = models.CharField(max_length=20, choices=TYPES, default="annuel")
    date = models.DateField()
    summary = models.TextField(blank=True, default="")
    conducted_by = models.CharField(max_length=255, blank=True, default="")


class EmployeeDocument(CompanyScopedModel):
    """Document administratif du dossier salarié."""

    CATEGORIES = (
        ("identite", "Pièce d'identité"),
        ("contrat", "Contrat signé"),
        ("diplome", "Diplôme"),
        ("medicale", "Visite médicale"),
        ("depart", "Document de départ (STC, attestation…)"),
        ("autre", "Autre"),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="documents")
    label = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=CATEGORIES, default="autre")
    file = models.FileField(upload_to="hr/documents/%Y/%m/")
    visible_to_employee = models.BooleanField(
        "Visible dans le portail salarié", default=False
    )
    retention_until = models.DateField("Conserver jusqu'au", null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
