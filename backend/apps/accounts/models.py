"""Utilisateurs, rôles et adhésions aux entreprises."""

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.permissions import Roles


class User(AbstractUser):
    """Utilisateur applicatif.

    Un utilisateur peut appartenir à plusieurs entreprises avec un rôle
    différent dans chacune (modèle `CompanyMembership`).
    """

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, blank=True, default="")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]


class CompanyMembership(TimeStampedModel):
    """Lien utilisateur <-> entreprise, porteur du rôle applicatif."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    company = models.ForeignKey(
        "organization.Company", on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=32, choices=Roles.CHOICES, default=Roles.SALARIE)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "company")

    def __str__(self):
        return f"{self.user} — {self.company} ({self.get_role_display()})"
