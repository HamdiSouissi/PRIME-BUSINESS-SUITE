"""Services métier RH : calcul des jours ouvrés et gestion des soldes."""

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import BusinessError

from .models import LeaveBalance, LeaveRequest


def jours_ouvres(start: date, end: date, half_start=False, half_end=False) -> Decimal:
    """Jours ouvrés (lundi-vendredi) entre deux dates incluses.

    NB : les jours fériés français ne sont pas retranchés ici — le comptage
    légal dépend du calendrier de l'entreprise (fériés, jours ouvrables). La
    saisie peut être ajustée manuellement par le valideur.
    """
    if end < start:
        return Decimal(0)
    days = Decimal(0)
    current = start
    while current <= end:
        if current.weekday() < 5:
            days += 1
        current += timedelta(days=1)
    if half_start and days > 0:
        days -= Decimal("0.5")
    if half_end and days > 0:
        days -= Decimal("0.5")
    return days


@transaction.atomic
def decider_absence(request_obj: LeaveRequest, decision: str, commentaire: str, user):
    """Valide ou refuse une demande d'absence, avec contrôle d'état."""
    decision_map = {"validee": "validee", "refusee": "refusee"}
    if decision not in decision_map:
        raise BusinessError("Décision inconnue.", code="decision_inconnue")
    if request_obj.status not in {"soumise", "brouillon"}:
        raise BusinessError(
            "Cette demande a déjà été traitée ou annulée.", code="transition_interdite"
        )
    request_obj.status = decision_map[decision]
    request_obj.manager_comment = commentaire
    request_obj.decided_by = user
    request_obj.decided_at = timezone.now()
    request_obj.save(
        update_fields=["status", "manager_comment", "decided_by", "decided_at", "updated_at"]
    )
    if request_obj.status == "validee":
        _debiter_solde(request_obj)
    return request_obj


def _debiter_solde(request_obj: LeaveRequest):
    """Débite le solde de congés de l'année de début d'absence."""
    solde, _ = LeaveBalance.objects.get_or_create(
        company=request_obj.company,
        employee=request_obj.employee,
        leave_type=request_obj.leave_type,
        year=request_obj.start_date.year,
    )
    solde.taken = solde.taken + request_obj.business_days
    solde.save(update_fields=["taken", "updated_at"])


@transaction.atomic
def annuler_absence(request_obj: LeaveRequest, user):
    """Annule une demande validée ou soumise, en recréditant le solde."""
    if request_obj.status not in {"soumise", "validee", "brouillon"}:
        raise BusinessError(
            "Seules les demandes en attente ou validées peuvent être annulées.",
            code="transition_interdite",
        )
    if request_obj.status == "validee":
        solde = LeaveBalance.objects.filter(
            employee=request_obj.employee,
            leave_type=request_obj.leave_type,
            year=request_obj.start_date.year,
        ).first()
        if solde:
            solde.taken = max(Decimal(0), solde.taken - request_obj.business_days)
            solde.save(update_fields=["taken", "updated_at"])
    request_obj.status = "annulee"
    request_obj.decided_by = user
    request_obj.decided_at = timezone.now()
    request_obj.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
    return request_obj
