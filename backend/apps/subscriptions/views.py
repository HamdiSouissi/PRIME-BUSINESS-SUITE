"""API des abonnements et des revenus récurrents."""

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessError
from apps.core.permissions import HasRole, ReadOnlyOrRole, Roles
from apps.core.viewsets import CompanyScopedViewSet

from . import services
from .models import Subscription, SubscriptionInvoice, SubscriptionStatus
from .serializers import SubscriptionInvoiceSerializer, SubscriptionSerializer

ABO_ROLES = (Roles.ADMIN, Roles.DIRECTION, Roles.FINANCE, Roles.COMPTABLE)


class SubscriptionViewSet(CompanyScopedViewSet):
    queryset = Subscription.objects.select_related("client").all()
    serializer_class = SubscriptionSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*ABO_ROLES, Roles.MANAGER))
    filterset_fields = ("status", "periodicity", "client", "auto_renew")
    search_fields = ("label", "client__name")

    def perform_create(self, serializer):
        serializer.save(company=self.request.company, created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="suspendre")
    def suspendre(self, request, pk=None):
        abo = self.get_object()
        if abo.status != SubscriptionStatus.ACTIF:
            raise BusinessError("Seul un abonnement actif peut être suspendu.", code="transition_interdite")
        abo.status = SubscriptionStatus.SUSPENDU
        abo.save(update_fields=["status", "updated_at"])
        return Response(SubscriptionSerializer(abo).data)

    @action(detail=True, methods=["post"], url_path="reactiver")
    def reactiver(self, request, pk=None):
        abo = self.get_object()
        if abo.status != SubscriptionStatus.SUSPENDU:
            raise BusinessError("Seul un abonnement suspendu peut être réactivé.", code="transition_interdite")
        abo.status = SubscriptionStatus.ACTIF
        abo.save(update_fields=["status", "updated_at"])
        return Response(SubscriptionSerializer(abo).data)

    @action(detail=True, methods=["post"], url_path="resilier")
    def resilier(self, request, pk=None):
        abo = self.get_object()
        if abo.status == SubscriptionStatus.RESILIE:
            raise BusinessError("Abonnement déjà résilié.", code="transition_interdite")
        abo.status = SubscriptionStatus.RESILIE
        abo.canceled_at = timezone.localdate()
        abo.cancel_reason = request.data.get("raison", "")
        abo.save(update_fields=["status", "canceled_at", "cancel_reason", "updated_at"])
        return Response(SubscriptionSerializer(abo).data)

    @action(detail=True, methods=["post"], url_path="changer-tarif")
    def changer_tarif(self, request, pk=None):
        """Historise tout changement de prix/remise."""
        abo = self.get_object()
        price = request.data.get("price_ht")
        discount = request.data.get("discount_percent")
        if price is None and discount is None:
            raise BusinessError("Rien à changer.", code="rien_a_changer")
        avant = {"price_ht": str(abo.price_ht), "discount_percent": str(abo.discount_percent)}
        if price is not None:
            abo.price_ht = price
        if discount is not None:
            abo.discount_percent = discount
        abo.history = abo.history + [{
            "at": timezone.now().isoformat(),
            "by": request.user.email,
            "avant": avant,
            "apres": {"price_ht": str(abo.price_ht), "discount_percent": str(abo.discount_percent)},
        }]
        abo.save()
        return Response(SubscriptionSerializer(abo).data)

    @action(detail=True, methods=["post"], url_path="facturer-maintenant",
            permission_classes=[IsAuthenticated, HasRole.of(*ABO_ROLES)])
    def facturer_maintenant(self, request, pk=None):
        abo = self.get_object()
        link = services.generer_facture_echeance(abo, request.user)
        if link is None:
            raise BusinessError("Aucune échéance à facturer pour cet abonnement.", code="aucune_echeance")
        return Response(SubscriptionInvoiceSerializer(link).data, status=201)

    @action(detail=False, methods=["post"], url_path="facturer-echues",
            permission_classes=[IsAuthenticated, HasRole.of(*ABO_ROLES)])
    def facturer_echues(self, request):
        count = services.generer_factures_echues_company(request.company, request.user)
        return Response({"factures_creees": count})

    @action(detail=False, methods=["get"], url_path="indicateurs")
    def indicateurs_view(self, request):
        return Response(services.indicateurs(request.company))


class SubscriptionInvoiceViewSet(CompanyScopedViewSet):
    queryset = SubscriptionInvoice.objects.select_related("subscription", "invoice").all()
    serializer_class = SubscriptionInvoiceSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*ABO_ROLES))
    http_method_names = ["get", "head", "options"]
    filterset_fields = ("subscription",)
