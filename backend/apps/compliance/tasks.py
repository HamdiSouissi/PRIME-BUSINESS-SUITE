import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.compliance.tasks.generer_obligations_a_venir")
def generer_obligations_a_venir():
    """Génère les instances d'obligations à venir pour toutes les entreprises."""
    from apps.organization.models import Company

    from .services import generer_instances

    for company in Company.objects.all():
        generer_instances(company)
    logger.info("Instances d'obligations régénérées.")
