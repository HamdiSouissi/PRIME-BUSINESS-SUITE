import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.subscriptions.tasks.generer_factures_echues")
def generer_factures_echues():
    """Tâche planifiée : facturation des échéances d'abonnements (idempotente)."""
    from apps.organization.models import Company

    from .services import generer_factures_echues_company

    total = 0
    for company in Company.objects.all():
        total += generer_factures_echues_company(company)
    logger.info("Factures d'abonnements générées : %s", total)
    return total
