"""Configuration Celery.

En développement, CELERY_TASK_ALWAYS_EAGER=True exécute les tâches de façon
synchrone : l'application reste pleinement fonctionnelle sans worker Redis.
En production, lancer : celery -A config worker -l info  (et beat pour le
planificateur).
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("prime_business_suite")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Génération des factures d'abonnements à échéance (idempotente).
    "subscriptions-facturation-quotidienne": {
        "task": "apps.subscriptions.tasks.generer_factures_echues",
        "schedule": 24 * 3600,
    },
    # Régénération des instances d'obligations de conformité à venir.
    "conformite-obligations-hebdomadaire": {
        "task": "apps.compliance.tasks.generer_obligations_a_venir",
        "schedule": 7 * 24 * 3600,
    },
    # Détection des factures clients échues.
    "facturation-retards-quotidien": {
        "task": "apps.invoicing.tasks.marquer_factures_echues",
        "schedule": 24 * 3600,
    },
}
