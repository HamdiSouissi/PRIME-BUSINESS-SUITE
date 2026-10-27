"""Tâches planifiées de facturation (exécutées par Celery beat ou à la demande)."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.invoicing.tasks.marquer_factures_echues")
def marquer_factures_echues():
    from apps.organization.models import Company

    from .services import marquer_factures_echues_company

    total = 0
    for company in Company.objects.all():
        total += marquer_factures_echues_company(company)
    logger.info("Factures marquées en retard : %s", total)
    return total
