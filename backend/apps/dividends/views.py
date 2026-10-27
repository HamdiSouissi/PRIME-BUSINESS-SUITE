"""API associés / capital / dividendes."""

from decimal import Decimal

from rest_framework import viewsets
from rest_framework.decorators import action
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessError
from apps.core.permissions import HasRole, ReadOnlyOrRole, Roles
from apps.core.viewsets import CompanyScopedViewSet

from . import services
from .models import (
    Associate,
    CapitalMovement,
    CurrentAccountEntry,
    DistributionDecision,
    DividendPayment,
)
from .serializers import (
    AssociateSerializer,
    CapitalMovementSerializer,
    CurrentAccountEntrySerializer,
    DistributionDecisionSerializer,
    DividendPaymentSerializer,
)

DIV_ROLES = (Roles.ADMIN, Roles.DIRECTION, Roles.FINANCE)


class AssociateViewSet(CompanyScopedViewSet):
    queryset = Associate.objects.all()
    serializer_class = AssociateSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*DIV_ROLES))
    search_fields = ("last_name", "first_name", "company_name")

    @action(detail=False, methods=["get"], url_path="registre")
    def registre(self, request):
        """Répartition actuelle du capital."""
        associes = Associate.objects.filter(company=request.company, exit_date__isnull=True)
        total = sum(a.shares for a in associes) or 1
        return Response(
            {
                "total_parts": total,
                "lignes": [
                    {
                        "associe": str(a),
                        "parts": a.shares,
                        "pourcentage": str((Decimal(100) * a.shares / total).quantize(Decimal('0.01'))),
                        "entree": a.entry_date.isoformat(),
                    }
                    for a in associes
                ],
            }
        )


class CapitalMovementViewSet(CompanyScopedViewSet):
    queryset = CapitalMovement.objects.select_related("associate").all()
    serializer_class = CapitalMovementSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*DIV_ROLES))
    ordering_fields = ("date",)


class CurrentAccountEntryViewSet(CompanyScopedViewSet):
    queryset = CurrentAccountEntry.objects.select_related("associate").all()
    serializer_class = CurrentAccountEntrySerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*DIV_ROLES))
    filterset_fields = ("associate", "entry_type")
    ordering_fields = ("date",)

    @action(detail=False, methods=["get"], url_path="soldes")
    def soldes(self, request):
        from collections import defaultdict
        from decimal import Decimal

        soldes = defaultdict(Decimal)
        for entry in CurrentAccountEntry.objects.filter(company=request.company).select_related("associate"):
            sens = Decimal(1) if entry.entry_type in {"apport", "interet"} else Decimal(-1)
            soldes[str(entry.associate)] += entry.amount * sens
        return Response({"soldes": {k: str(v) for k, v in soldes.items()}})


class DistributionDecisionViewSet(CompanyScopedViewSet):
    queryset = DistributionDecision.objects.prefetch_related("paiements__associate").all()
    serializer_class = DistributionDecisionSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*DIV_ROLES))
    ordering_fields = ("fiscal_year",)

    @action(detail=True, methods=["get"], url_path="distribuable")
    def distribuable(self, request, pk=None):
        """Calcule la somme distribuable d'après les données déclarées."""
        return Response(services.calculer_somme_distribuable(request.company, self.get_object()))

    @action(detail=True, methods=["post"], url_path="decider")
    def decider(self, request, pk=None):
        from decimal import Decimal

        decision = self.get_object()
        montant = Decimal(str(request.data.get("montant", "0")))
        services.decider_distribution(decision, montant, request.user,
                                      document=request.FILES.get("document"))
        return Response(DistributionDecisionSerializer(decision).data)

    @action(detail=True, methods=["get"], url_path="paiements")
    def paiements(self, request, pk=None):
        decision = self.get_object()
        return Response(DividendPaymentSerializer(decision.paiements.all(), many=True).data)


class DividendPaymentViewSet(CompanyScopedViewSet):
    queryset = DividendPayment.objects.select_related("decision", "associate").all()
    serializer_class = DividendPaymentSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*DIV_ROLES))
    filterset_fields = ("decision", "associate")
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=True, methods=["post"], url_path="marquer-payee",
            permission_classes=[IsAuthenticated, HasRole.of(*DIV_ROLES)])
    def marquer_payee(self, request, pk=None):
        from django.db.transaction import atomic
        from django.utils import timezone

        paiement = self.get_object()
        date_str = request.data.get("date")
        date_valeur = timezone.localdate()
        if date_str:
            from datetime import datetime

            date_valeur = datetime.strptime(date_str, "%Y-%m-%d").date()
        with atomic():
            services.marquer_payee(paiement, request.user, date_valeur,
                                   preuve=request.FILES.get("preuve"))
        # Tous les paiements soldés → décision payée
        decision = paiement.decision
        if not decision.paiements.filter(paid_on__isnull=True).exists():
            decision.status = decision.status.PAYEE
            decision.save(update_fields=["status", "updated_at"])
        return Response(DividendPaymentSerializer(paiement).data)
