# Charge l'application Celery lors du démarrage de Django (si disponible).
try:  # pragma: no cover - dépend de l'installation de celery
    from .celery import app as celery_app

    __all__ = ("celery_app",)
except Exception:  # Celery est facultatif en développement local
    celery_app = None
