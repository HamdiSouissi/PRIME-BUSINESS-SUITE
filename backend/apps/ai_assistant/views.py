"""API de l'assistant IA : fournisseurs, tests, modèles, fonctionnalités."""

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import BusinessError
from apps.core.permissions import HasRole, ReadOnlyOrRole, Roles
from apps.core.secrets import chiffrer
from apps.core.viewsets import CompanyScopedViewSet

from . import features as ia_features
from .models import AIFeature, AIProvider, AIUsageLog, FeatureRouting
from .providers import client_pour, generer
from .serializers import (
    AIProviderSerializer,
    AIProviderUpdateSerializer,
    AIUsageLogSerializer,
    FeatureRoutingSerializer,
)

AI_ADMIN_ROLES = (Roles.ADMIN,)
AI_USAGE_ROLES = (Roles.ADMIN, Roles.DIRECTION, Roles.FINANCE, Roles.RH, Roles.COMPTABLE, Roles.MANAGER)


class AIProviderViewSet(CompanyScopedViewSet):
    """Paramètres → Intelligence artificielle → Fournisseurs."""

    queryset = AIProvider.objects.all()
    permission_classes = (IsAuthenticated, HasRole.of(*AI_ADMIN_ROLES))
    filterset_fields = ("kind", "is_enabled")

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return AIProviderUpdateSerializer
        return AIProviderSerializer

    def perform_create(self, serializer):
        api_key = self.request.data.get("api_key", "")
        provider = serializer.save(
            company=self.request.company,
            api_key_encrypted=chiffrer(api_key) if api_key else "",
        )
        return provider

    def perform_update(self, serializer):
        provider = self.get_object()
        api_key = self.request.data.get("api_key")
        if api_key:  # seulement si une nouvelle clé est fournie
            provider.api_key_encrypted = chiffrer(api_key)
            provider.save(update_fields=["api_key_encrypted"])
        serializer.save()

    @action(detail=True, methods=["post"], url_path="tester")
    def tester(self, request, pk=None):
        """Test de connexion réel au fournisseur (statut persisté)."""
        provider = self.get_object()
        client = client_pour(provider)
        resultat = client.check()
        provider.last_checked_at = timezone.now()
        provider.last_status = "ok" if resultat.get("ok") else "erreur"
        provider.last_error = "" if resultat.get("ok") else resultat.get("detail", "")
        if resultat.get("ok") and resultat.get("modeles"):
            provider.available_models = resultat["modeles"]
        provider.save(update_fields=["last_status", "last_checked_at", "last_error", "available_models"])
        return Response(resultat)

    @action(detail=True, methods=["get"], url_path="modeles")
    def modeles(self, request, pk=None):
        """Liste dynamique des modèles disponibles (GET /models ou équivalent)."""
        provider = self.get_object()
        try:
            modeles = client_pour(provider).list_models()
        except Exception as exc:
            raise BusinessError(f"Impossible de lister les modèles : {exc}", code="ia_indisponible")
        provider.available_models = [m.get("id", "") for m in modeles]
        provider.save(update_fields=["available_models"])
        return Response({"modeles": modeles})


class FeatureRoutingViewSet(CompanyScopedViewSet):
    """Choix du fournisseur par fonctionnalité."""

    queryset = FeatureRouting.objects.select_related("provider", "fallback_provider").all()
    serializer_class = FeatureRoutingSerializer
    permission_classes = (IsAuthenticated, HasRole.of(*AI_ADMIN_ROLES))

    def get_queryset(self):
        return super().get_queryset()


class AIUsageLogViewSet(CompanyScopedViewSet):
    """Journal d'usage de l'IA (traçabilité, coûts)."""

    queryset = AIUsageLog.objects.select_related("user").all()
    serializer_class = AIUsageLogSerializer
    permission_classes = (IsAuthenticated, HasRole.of(*AI_ADMIN_ROLES))
    http_method_names = ["get", "head", "options"]
    filterset_fields = ("feature", "provider_kind", "success")


class AIStatusView(APIView):
    """État global de l'IA : activable par tout rôle (lecture)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        providers = AIProvider.objects.filter(company=request.company)
        routages = FeatureRouting.objects.filter(company=request.company).select_related("provider")
        return Response({
            "ia_disponible": providers.filter(is_enabled=True).exists(),
            "fournisseurs": AIProviderSerializer(providers, many=True).data,
            "routages": FeatureRoutingSerializer(routages, many=True).data,
            "fonctionnalites": [{"value": value, "label": label} for value, label in AIFeature.choices],
        })


class AIAssistView(APIView):
    """Point d'entrée des fonctionnalités IA.

    Toujours facultatif : répond 503 avec un message clair si l'IA est
    désactivée ou injoignable — l'application reste fonctionnelle sans elle.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        action_name = request.data.get("action")
        data = request.data.get("data", {})
        company = request.company
        try:
            if action_name == "resumer_document":
                resultat = ia_features.resumer_document(company, data.get("texte", ""), user=request.user)
            elif action_name == "extraire_facture":
                resultat = ia_features.extraire_facture(company, data.get("texte", ""), user=request.user)
            elif action_name == "brouillon_contrat":
                resultat = ia_features.brouillon_contrat(
                    company, data.get("contexte", ""), data.get("type_document", "prestation"), user=request.user
                )
            elif action_name == "synthese_tresorerie":
                from apps.treasury.services import previsionnel

                resultat = ia_features.synthese_tresorerie(
                    company, previsionnel(company, data.get("scenario", "central")), user=request.user
                )
            elif action_name == "expliquer_indicateur":
                resultat = ia_features.expliquer_indicateur(
                    company, data.get("nom", ""), data.get("valeur", ""),
                    data.get("definitions", ""), user=request.user,
                )
            elif action_name == "rediger_email":
                resultat = ia_features.rediger_email(company, data.get("contexte", ""), user=request.user)
            elif action_name == "classifier_depense":
                resultat = ia_features.classifier_depense(
                    company, data.get("libelle", ""), data.get("categories", []),
                    data.get("marchand", ""), user=request.user,
                )
            elif action_name == "detecter_anomalies":
                resultat = ia_features.detecter_anomalies(company, data.get("donnees", ""), user=request.user)
            elif action_name == "preparer_rapport":
                resultat = ia_features.preparer_rapport(
                    company, data.get("donnees", ""), data.get("sujet", ""), user=request.user
                )
            elif action_name == "recherche_nl":
                resultat = self._recherche_nl(company, request.user, data.get("question", ""))
            else:
                return Response(
                    {"detail": "Action inconnue.", "code": "action_inconnue"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except BusinessError as exc:
            return Response({"detail": exc.message, "code": exc.code},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(resultat)

    def _recherche_nl(self, company, user, question: str) -> dict:
        """Recherche en langage naturel dans les données AUTORISÉES.

        Périmètre limité : indicateurs agrégés (pas de contenu de paie ni
        coordonnées bancaires)."""
        from django.db.models import Sum

        from apps.invoicing.models import Invoice, InvoiceStatus
        from apps.hr.models import Employee
        from apps.subscriptions.services import indicateurs as mrr_indicateurs

        contexte = {
            "salaries_actifs": Employee.objects.filter(company=company, status="actif").count(),
            "factures_impayees": Invoice.objects.filter(
                company=company,
                status__in=(InvoiceStatus.EMISE, InvoiceStatus.EN_RETARD, InvoiceStatus.PARTIELLEMENT_PAYEE),
            ).aggregate(total=Sum("total_ttc")),
            "mrr": mrr_indicateurs(company),
        }
        import json

        reponse = generer(
            company,
            AIFeature.RECHERCHE_NL,
            [
                {"role": "system", "content": (
                    "Répondez en français en utilisant UNIQUEMENT les données du contexte "
                    "(indicateurs agrégés autorisés). Si insuffisant, dites-le et précisez "
                    "où trouver l'information dans l'application."
                )},
                {"role": "user", "content": f"Question : {question}\n\nContexte agrégé :\n{json.dumps(contexte, ensure_ascii=False, default=str)[:8000]}"},
            ],
            user=user,
        )
        return {"reponse": reponse.content, "modele": reponse.model,
                "perimetre": "indicateurs agrégés uniquement"}
