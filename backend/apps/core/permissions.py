"""Permissions DRF fondées sur les rôles métier et l'entreprise active."""

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.permissions import IsAuthenticated as _DRFIsAuthenticated


class IsAuthenticated(_DRFIsAuthenticated):
    """Authentification + résolution de l'entreprise active de la requête.

    Toutes les vues de l'API utilisent cette classe (import en remplacement de
    celle de DRF) : l'isolation multi-entreprise est systématiquement posée.
    """

    def has_permission(self, request, view):
        autorise = super().has_permission(request, view)
        if autorise:
            active_company(request)
        return autorise


class Roles:
    """Rôles applicatifs par défaut (section 16 du cahier des charges)."""

    ADMIN = "administrateur"
    DIRECTION = "direction"
    RH = "ressources_humaines"
    PAIE = "gestionnaire_paie"
    COMPTABLE = "comptable"
    FINANCE = "responsable_financier"
    MANAGER = "manager"
    SALARIE = "salarie"

    CHOICES = (
        (ADMIN, "Administrateur"),
        (DIRECTION, "Direction"),
        (RH, "Ressources humaines"),
        (PAIE, "Gestionnaire de paie"),
        (COMPTABLE, "Comptable"),
        (FINANCE, "Responsable financier"),
        (MANAGER, "Manager"),
        (SALARIE, "Salarié"),
    )


def active_company(request):
    """Résout (et mémorise) l'entreprise active de la requête.

    Ordre : contexte posé par l'authentification JWT → en-tête X-Company-Id →
    première adhésion active de l'utilisateur. Mise en cache sur la requête.
    """
    company = getattr(request, "company", None)
    if company is not None:
        return company
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return None
    try:
        from apps.accounts.models import CompanyMembership

        memberships = CompanyMembership.objects.filter(user=user, is_active=True)
        company_id = request.headers.get("X-Company-Id")
        membership = None
        if company_id and str(company_id).isdigit():
            membership = memberships.filter(company_id=int(company_id)).first()
        if membership is None:
            membership = memberships.first()
        if membership is not None:
            request.company = membership.company
            request.membership = membership
            return membership.company
    except Exception:  # pragma: no cover
        pass
    return None


def user_role(request) -> str | None:
    membership = getattr(request, "membership", None)
    if membership is not None:
        return membership.role
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        if user.is_superuser:
            return Roles.ADMIN
        if active_company(request) is not None:
            return request.membership.role
    return None


class HasRole(BasePermission):
    """Autorise uniquement certains rôles (vérifiés côté serveur)."""

    roles: tuple = ()

    def has_permission(self, request, view):
        role = user_role(request)
        if role is None:
            return False
        return role in self.roles

    @classmethod
    def of(cls, *roles):
        return type(f"HasRole_{hash(roles)}", (cls,), {"roles": roles})


class ReadOnlyOrRole(HasRole):
    """Lecture pour tous les rôles authentifiés, écriture restreinte."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return user_role(request) is not None
        return super().has_permission(request, view)
