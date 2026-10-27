"""Gestion centralisée des erreurs API : réponses uniformes en français."""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class BusinessError(Exception):
    """Erreur métier contrôlée (ex. transition d'état interdite)."""

    def __init__(self, message: str, code: str = "business_error"):
        super().__init__(message)
        self.message = message
        self.code = code


class NotAllowedTransition(BusinessError):
    def __init__(self, message: str):
        super().__init__(message, code="invalid_transition")


def api_exception_handler(exc, context):
    if isinstance(exc, BusinessError):
        return Response(
            {"detail": exc.message, "code": exc.code},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(exc, DjangoValidationError):
        return Response(
            {"detail": " ".join(exc.messages), "code": "validation_error"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)
    if response is not None:
        payload = response.data
        if isinstance(payload, dict):
            payload.setdefault("code", "api_error")
        return response

    logger.exception("Erreur non gérée", exc_info=exc)
    return Response(
        {"detail": "Erreur interne du serveur.", "code": "internal_error"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
