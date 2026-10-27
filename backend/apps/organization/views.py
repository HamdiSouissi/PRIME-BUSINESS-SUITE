from rest_framework import viewsets
from apps.core.permissions import IsAuthenticated

from apps.core.permissions import ReadOnlyOrRole, Roles

from .models import Company
from .serializers import CompanySerializer


class CompanyViewSet(viewsets.ModelViewSet):
    """Gestion des entreprises.

    - Lecture : tout utilisateur membre.
    - Écriture : administrateur ou direction.
    Un utilisateur ne voit que les entreprises auxquelles il appartient.
    """

    serializer_class = CompanySerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(Roles.ADMIN, Roles.DIRECTION))

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Company.objects.all().order_by("name")
        return Company.objects.filter(
            memberships__user=user, memberships__is_active=True
        ).distinct().order_by("name")
