"""Middlewares : contexte d'entreprise actif et journal d'audit HTTP."""

import logging

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class CompanyMiddleware(MiddlewareMixin):
    """Résout l'entreprise active de la requête.

    - L'utilisateur authentifié voit ses adhésions (`CompanyMembership`).
    - L'en-tête optionnel `X-Company-Id` permet de basculer d'entreprise si
      l'utilisateur appartient à plusieurs sociétés.
    - `request.company` vaut None pour les super-utilisateurs sans adhésion
      explicite et pour les utilisateurs anonymes.
    """

    def process_request(self, request):
        request.company = None
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None

        from apps.accounts.models import CompanyMembership

        memberships = CompanyMembership.objects.filter(user=user, is_active=True)
        company_id = request.headers.get("X-Company-Id")
        membership = None
        if company_id and company_id.isdigit():
            membership = memberships.filter(company_id=int(company_id)).first()
        if membership is None:
            membership = memberships.first()
        if membership is not None:
            request.company = membership.company
            request.membership = membership
        else:
            request.membership = None
        return None


class AuditLogMiddleware(MiddlewareMixin):
    """Journalise côté serveur toutes les requêtes d'écriture (POST/PUT…)."""

    SENSITIVE_HINTS = {
        "payroll": "paie",
        "payslips": "paie",
        "bank": "finance",
        "treasury": "finance",
        "payments": "finance",
        "dividends": "finance",
        "auth": "securite",
        "users": "securite",
    }

    WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def process_response(self, request, response):
        try:
            if request.method not in self.WRITE_METHODS:
                return response
            if not request.path.startswith("/api/"):
                return response
            # Ne jamais journaliser les corps de requêtes (peuvent contenir
            # des mots de passe ou des données de paie).
            from apps.core.models import AuditLog

            sensitivity = "info"
            for hint, level in self.SENSITIVE_HINTS.items():
                if hint in request.path:
                    sensitivity = level
                    break

            user = request.user if request.user.is_authenticated else None
            AuditLog.objects.create(
                user=user,
                company=getattr(request, "company", None),
                action=f"{request.method} {request.path}",
                method=request.method,
                path=request.path[:500],
                status_code=getattr(response, "status_code", None),
                ip_address=_client_ip(request),
                sensitivity=sensitivity,
            )
        except Exception:  # pragma: no cover - le journal ne doit jamais casser l'API
            logger.exception("Échec d'écriture du journal d'audit")
        return response
