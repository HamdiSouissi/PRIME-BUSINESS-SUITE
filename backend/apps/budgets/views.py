"""API du pilotage budgétaire."""

from rest_framework import viewsets
from rest_framework.decorators import action
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasRole, ReadOnlyOrRole, Roles
from apps.core.viewsets import CompanyScopedViewSet

from . import services
from .models import Budget, BudgetLine
from .serializers import BudgetLineSerializer, BudgetSerializer

PILOTAGE_ROLES = (Roles.ADMIN, Roles.DIRECTION, Roles.FINANCE)


class BudgetViewSet(CompanyScopedViewSet):
    queryset = Budget.objects.prefetch_related("lines").all()
    serializer_class = BudgetSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*PILOTAGE_ROLES))
    filterset_fields = ("year", "is_active")

    @action(detail=True, methods=["get"], url_path="analyse")
    def analyse(self, request, pk=None):
        return Response(services.budget_vs_realise(self.get_object()))

    @action(detail=True, methods=["get"], url_path="seuil-de-rentabilite")
    def seuil(self, request, pk=None):
        return Response(services.seuil_de_rentabilite(self.get_object()) or {"message": "Données insuffisantes."})

    @action(detail=False, methods=["get"], url_path="bfr")
    def bfr(self, request):
        return Response(services.besoin_fonds_roulement(request.company))


class BudgetLineViewSet(CompanyScopedViewSet):
    queryset = BudgetLine.objects.select_related("budget").all()
    serializer_class = BudgetLineSerializer
    permission_classes = (IsAuthenticated, HasRole.of(*PILOTAGE_ROLES))
    filterset_fields = ("budget", "nature")
    ordering_fields = ("label",)
