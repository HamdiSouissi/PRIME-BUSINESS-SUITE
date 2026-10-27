"""API du centre de conformité."""

from rest_framework import viewsets
from rest_framework.decorators import action
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessError
from apps.core.permissions import HasRole, ReadOnlyOrRole, Roles
from apps.core.viewsets import CompanyScopedViewSet

from . import services
from .models import ObligationDefinition, ObligationInstance
from .serializers import ObligationDefinitionSerializer, ObligationInstanceSerializer

CONF_ROLES = (Roles.ADMIN, Roles.DIRECTION, Roles.RH, Roles.PAIE, Roles.COMPTABLE, Roles.FINANCE)


class ObligationDefinitionViewSet(viewsets.ModelViewSet):
    """Catalogue global des obligations (admin seul en écriture)."""

    queryset = ObligationDefinition.objects.all()
    serializer_class = ObligationDefinitionSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(Roles.ADMIN))
    filterset_fields = ("category", "periodicity", "active")
    search_fields = ("code", "label")

    @action(detail=False, methods=["post"], url_path="initialiser",
            permission_classes=[IsAuthenticated, HasRole.of(Roles.ADMIN)])
    def initialiser(self, request):
        services.initialiser_catalogue()
        return Response({"detail": "Catalogue initialisé."})


class ObligationInstanceViewSet(CompanyScopedViewSet):
    queryset = ObligationInstance.objects.select_related("definition", "completed_by").all()
    serializer_class = ObligationInstanceSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*CONF_ROLES))
    filterset_fields = ("status", "definition__category", "due_date")
    ordering_fields = ("due_date",)

    @action(detail=False, methods=["get"], url_path="tableau-de-bord")
    def tableau_de_bord(self, request):
        return Response(services.tableau_de_bord(request.company))

    @action(detail=False, methods=["post"], url_path="generer",
            permission_classes=[IsAuthenticated, HasRole.of(Roles.ADMIN, Roles.DIRECTION)])
    def generer(self, request):
        count = services.generer_instances(request.company)
        return Response({"instances_creees": count})

    @action(detail=True, methods=["post"], url_path="marquer-faite")
    def marquer_faite(self, request, pk=None):
        instance = self.get_object()
        from django.utils import timezone

        instance.status = "faite"
        instance.completed_at = timezone.localdate()
        instance.completed_by = request.user
        if request.FILES.get("preuve"):
            instance.proof = request.FILES["preuve"]
        instance.note = request.data.get("note", instance.note)
        instance.save()
        return Response(ObligationInstanceSerializer(instance).data)

    @action(detail=True, methods=["post"], url_path="marquer-non-applicable")
    def non_applicable(self, request, pk=None):
        instance = self.get_object()
        note = request.data.get("note", "").strip()
        if not note:
            raise BusinessError(
                "Un motif est obligatoire pour écarter une obligation.", code="motif_requis"
            )
        instance.status = "non_applicable"
        instance.note = note
        instance.completed_by = request.user
        from django.utils import timezone

        instance.completed_at = timezone.localdate()
        instance.save()
        return Response(ObligationInstanceSerializer(instance).data)
