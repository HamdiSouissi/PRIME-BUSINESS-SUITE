"""API trésorerie : comptes, opérations, import, rapprochement, prévisions."""

from rest_framework import viewsets
from rest_framework.decorators import action
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessError
from apps.core.permissions import HasRole, ReadOnlyOrRole, Roles
from apps.core.viewsets import CompanyScopedViewSet

from . import services
from .models import BankAccount, BankTransaction, CashEvent
from .serializers import BankAccountSerializer, BankTransactionSerializer, CashEventSerializer

FIN_ROLES = (Roles.ADMIN, Roles.FINANCE, Roles.COMPTABLE, Roles.DIRECTION)


class BankAccountViewSet(CompanyScopedViewSet):
    queryset = BankAccount.objects.all()
    serializer_class = BankAccountSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*FIN_ROLES))
    filterset_fields = ("is_active", "is_main")


class BankTransactionViewSet(CompanyScopedViewSet):
    queryset = BankTransaction.objects.select_related("bank_account", "payment").all()
    serializer_class = BankTransactionSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*FIN_ROLES))
    filterset_fields = ("bank_account", "reconciled", "date")
    search_fields = ("label", "reference")
    ordering_fields = ("date", "amount")

    @action(detail=False, methods=["post"], url_path="importer-csv",
            permission_classes=[IsAuthenticated, HasRole.of(*FIN_ROLES)])
    def importer_csv(self, request):
        account_id = request.data.get("bank_account")
        fichier = request.FILES.get("fichier")
        if not account_id or not fichier:
            raise BusinessError("Paramètres requis : bank_account, fichier.", code="parametres")
        account = BankAccount.objects.filter(company=request.company, pk=account_id).first()
        if account is None:
            raise BusinessError("Compte inconnu.", code="compte_inconnu")
        resultat = services.importer_csv(account, fichier.read(), request.user)
        return Response(resultat)

    @action(detail=True, methods=["post"], url_path="rapprocher",
            permission_classes=[IsAuthenticated, HasRole.of(*FIN_ROLES)])
    def rapprocher(self, request, pk=None):
        from apps.invoicing.models import Payment

        transaction_obj = self.get_object()
        payment_id = request.data.get("payment")
        payment = Payment.objects.filter(company=request.company, pk=payment_id).first()
        if payment is None:
            raise BusinessError("Règlement inconnu.", code="paiement_inconnu")
        services.rapprocher(transaction_obj, payment, request.user)
        return Response(BankTransactionSerializer(transaction_obj).data)

    @action(detail=True, methods=["get"], url_path="suggestions")
    def suggestions(self, request, pk=None):
        """Règlements candidats pour le rapprochement manuel."""
        transaction_obj = self.get_object()
        paiements = services.suggestions_rapprochement(transaction_obj)
        from apps.invoicing.serializers import PaymentSerializer

        return Response(PaymentSerializer(paiements, many=True).data)

    @action(detail=False, methods=["get"], url_path="previsionnel")
    def previsionnel(self, request):
        scenario = request.query_params.get("scenario", "central")
        if scenario not in services.SCENARIOS:
            raise BusinessError("Scenario attendu : optimiste | central | prudent.", code="scenario")
        return Response(services.previsionnel(request.company, scenario))

    @action(detail=False, methods=["get"], url_path="synthese")
    def synthese(self, request):
        """Synthèse : soldes bancaires et solde comptable 512 (non confondus)."""
        comptes = BankAccount.objects.filter(company=request.company, is_active=True)
        return Response(
            {
                "comptes": BankAccountSerializer(comptes, many=True).data,
                "solde_bancaire_total": sum(services.solde_bancaire(c) for c in comptes),
                "solde_comptable_512": services.solde_comptable_banque(request.company),
                "note": "Le solde bancaire (disponible) et le solde comptable sont deux mesures distinctes.",
            }
        )


class CashEventViewSet(CompanyScopedViewSet):
    queryset = CashEvent.objects.all()
    serializer_class = CashEventSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*FIN_ROLES))
    filterset_fields = ("direction", "is_realized", "is_recurring_monthly")
    ordering_fields = ("expected_date",)
