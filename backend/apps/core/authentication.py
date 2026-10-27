"""Authentification JWT enrichie du contexte d'entreprise.

L'authentification DRF a lieu lors de l'initialisation de la vue (et non dans
un middleware Django) : c'est ici que `request.company` et
`request.membership` sont résolus pour les appels API.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication


class JWTCompanyAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        _resoudre_entreprise(request, user)
        return result


def _resoudre_entreprise(request, user):
    """Résout l'entreprise active à partir de l'en-tête X-Company-Id ou de la
    première adhésion active de l'utilisateur."""
    from apps.accounts.models import CompanyMembership

    # Le middleware d'audit lit la requête Django sous-jacente (et non
    # l'enveloppe DRF) : on répercute donc le contexte sur les deux objets.
    django_request = getattr(request, "_request", request)

    request.company = getattr(request, "company", None)
    if request.company is not None:
        django_request.company = request.company
        return
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
        django_request.company = membership.company
        django_request.membership = membership
    else:
        request.membership = None
        django_request.membership = None
