"""Workflow des notes de frais et contrôles de politique / doublons."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import BusinessError

from .models import ExpenseLine, ExpenseReport, ExpenseReportStatus


def recalculer_total(report: ExpenseReport):
    total = sum(line.amount_ttc for line in report.lines.all())
    report.total_amount = total
    report.save(update_fields=["total_amount", "updated_at"])
    return total


def appliquer_controles(line: ExpenseLine):
    """Marque les dépassements de politique et les doublons suspectés.

    Aucun blocage automatique : un humain décide (cahier des charges §11).
    """
    category = line.category
    if category.max_amount and line.amount_ttc > category.max_amount:
        line.over_policy = True
    # Doublon suspecté : même salarié, même date, même montant, même commerçant
    suspects = ExpenseLine.objects.filter(
        company=line.company,
        report__employee=line.report.employee,
        date=line.date,
        amount_ttc=line.amount_ttc,
        merchant=line.merchant,
    ).exclude(pk=line.pk)
    if suspects.exists():
        line.duplicate_suspect = True
    line.save(update_fields=["over_policy", "duplicate_suspect", "updated_at"])


@transaction.atomic
def soumettre(report: ExpenseReport):
    if report.status != ExpenseReportStatus.BROUILLON:
        raise BusinessError("Note déjà soumise.", code="transition_interdite")
    if not report.lines.exists():
        raise BusinessError("Une note de frais vide ne peut pas être soumise.", code="note_vide")
    # Justificatif obligatoire selon la politique de la catégorie
    manquants = [
        line for line in report.lines.select_related("category")
        if line.category.receipt_required and not line.receipt
    ]
    if manquants:
        raise BusinessError(
            f"{len(manquants)} ligne(s) sans justificatif obligatoire.", code="justificatif_manquant"
        )
    recalculer_total(report)
    report.status = ExpenseReportStatus.SOUMISE
    report.submitted_at = timezone.now()
    report.save(update_fields=["status", "submitted_at", "total_amount", "updated_at"])
    return report


@transaction.atomic
def decider(report: ExpenseReport, decision: str, commentaire: str, user):
    if report.status != ExpenseReportStatus.SOUMISE:
        raise BusinessError("Seule une note soumise peut recevoir une décision.", code="transition_interdite")
    if decision not in {"validee", "refusee"}:
        raise BusinessError("Décision attendue : validee | refusee.", code="decision_inconnue")
    if decision == "validee":
        lignes_hors_politique = report.lines.filter(over_policy=True).count()
        if lignes_hors_politique and not request_override_ok(commentaire):
            raise BusinessError(
                "Des lignes dépassent la politique de remboursement : une décision "
                "motivée est obligatoire (commentaire requis).",
                code="hors_politique",
            )
    report.status = ExpenseReportStatus.VALIDEE if decision == "validee" else ExpenseReportStatus.REFUSEE
    report.decision_comment = commentaire
    report.decided_by = user
    report.decided_at = timezone.now()
    report.save(update_fields=["status", "decision_comment", "decided_by", "decided_at", "updated_at"])
    return report


def request_override_ok(commentaire: str) -> bool:
    """Le dépassement de politique exige un commentaire motivé (>= 10 caractères)."""
    return bool(commentaire and len(commentaire.strip()) >= 10)


@transaction.atomic
def marquer_remboursee(report: ExpenseReport, date_remboursement=None):
    if report.status != ExpenseReportStatus.VALIDEE:
        raise BusinessError("Seule une note validée peut être remboursée.", code="transition_interdite")
    report.status = ExpenseReportStatus.REMBOURSEE
    report.reimbursed_at = date_remboursement or timezone.localdate()
    report.save(update_fields=["status", "reimbursed_at", "updated_at"])
    return report
