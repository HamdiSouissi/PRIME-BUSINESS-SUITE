"""API comptable : plan, journaux, exercices, écritures, rapports, export."""

from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessError
from apps.core.permissions import HasRole, ReadOnlyOrRole, Roles
from apps.core.viewsets import CompanyScopedViewSet

from . import services
from .models import Account, EntryStatus, FiscalYear, Journal, JournalEntry
from .seed_pcg import peupler_plan_comptable
from .serializers import (
    AccountSerializer,
    FiscalYearSerializer,
    JournalEntrySerializer,
    JournalSerializer,
)

COMPTA_ROLES = (Roles.ADMIN, Roles.COMPTABLE, Roles.FINANCE)
LECTURE_EXTRA = (Roles.DIRECTION,)


class AccountViewSet(CompanyScopedViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*COMPTA_ROLES))
    filterset_fields = ("account_class", "account_type", "is_active")
    search_fields = ("number", "label")

    @action(detail=False, methods=["post"], url_path="plan-par-defaut",
            permission_classes=[IsAuthenticated, HasRole.of(*COMPTA_ROLES)])
    def plan_par_defaut(self, request):
        peupler_plan_comptable(request.company)
        return Response({"detail": "Plan comptable général initialisé."})


class JournalViewSet(CompanyScopedViewSet):
    queryset = Journal.objects.all()
    serializer_class = JournalSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*COMPTA_ROLES))


class FiscalYearViewSet(CompanyScopedViewSet):
    queryset = FiscalYear.objects.all()
    serializer_class = FiscalYearSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*COMPTA_ROLES))

    @action(detail=True, methods=["post"], url_path="verrouiller",
            permission_classes=[IsAuthenticated, HasRole.of(*COMPTA_ROLES)])
    def verrouiller(self, request, pk=None):
        fy = self.get_object()
        fy.status = "verrouille"
        fy.save(update_fields=["status"])
        return Response(FiscalYearSerializer(fy).data)

    @action(detail=True, methods=["post"], url_path="cloturer",
            permission_classes=[IsAuthenticated, HasRole.of(*COMPTA_ROLES)])
    def cloturer(self, request, pk=None):
        """Clôture : aucune écriture ne sera plus acceptée sur l'exercice."""
        fy = self.get_object()
        fy.status = "cloture"
        fy.save(update_fields=["status"])
        return Response(FiscalYearSerializer(fy).data)

    @action(detail=True, methods=["get"], url_path="export-fec",
            permission_classes=[IsAuthenticated, HasRole.of(*COMPTA_ROLES)])
    def export_fec(self, request, pk=None):
        """Export de préparation pour l'expert-comptable (non certifié FEC)."""
        fy = self.get_object()
        contenu = services.export_fec(request.company, fy)
        response = HttpResponse(contenu, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="export-comptable-{fy.start_date.year}.csv"'
        return response


class JournalEntryViewSet(CompanyScopedViewSet):
    queryset = JournalEntry.objects.select_related("journal", "created_by", "validated_by").prefetch_related("lines__account").all()
    serializer_class = JournalEntrySerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*COMPTA_ROLES))
    filterset_fields = ("journal__code", "status", "date")
    search_fields = ("reference", "label")
    ordering_fields = ("date", "reference")

    def perform_create(self, serializer):
        """Création pilotée par le service (contrôle d'équilibre)."""
        data = serializer.validated_data
        lignes = self.request.data.get("lignes", [])
        entry = services.creer_ecriture(
            company=self.request.company,
            journal_code=data["journal"].code,
            date_valeur=data["date"],
            label=data["label"],
            lignes=lignes,
            user=self.request.user,
            valider=bool(self.request.data.get("valider", False)),
        )
        serializer.instance = entry

    def perform_update(self, serializer):
        entry = self.get_object()
        if entry.status != EntryStatus.BROUILLON:
            raise BusinessError(
                "Écriture validée : modification interdite. Corrigez par contre-passation.",
                code="ecriture_gelee",
            )
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        entry = self.get_object()
        if entry.status != EntryStatus.BROUILLON:
            raise BusinessError(
                "Une écriture validée ne se supprime pas : contre-passez-la.",
                code="suppression_interdite",
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="valider",
            permission_classes=[IsAuthenticated, HasRole.of(*COMPTA_ROLES)])
    def valider(self, request, pk=None):
        entry = services.valider_ecriture(self.get_object(), request.user)
        return Response(JournalEntrySerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="contre-passer",
            permission_classes=[IsAuthenticated, HasRole.of(*COMPTA_ROLES)])
    def contre_passer(self, request, pk=None):
        """Correction traçable : l'écriture originale reste inchangée."""
        entry = services.contre_passer(
            self.get_object(), request.user, motif=request.data.get("motif", "")
        )
        return Response(JournalEntrySerializer(entry).data, status=201)

    @action(detail=False, methods=["get"], url_path="balance")
    def balance(self, request):
        fy = self._exercice(request)
        return Response({"balance": services.balance_generale(request.company, fy)})

    @action(detail=False, methods=["get"], url_path="grand-livre")
    def grand_livre(self, request):
        """Grand livre : lignes détaillées, filtrable par compte."""
        qs = self.get_queryset().filter(status__in=(EntryStatus.VALIDEE, EntryStatus.CONTRE_PASSEE))
        compte = request.query_params.get("compte")
        journal = request.query_params.get("journal")
        date_debut = request.query_params.get("date_debut")
        date_fin = request.query_params.get("date_fin")
        if compte:
            qs = qs.filter(lines__account__number__startswith=compte)
        if journal:
            qs = qs.filter(journal__code=journal)
        if date_debut:
            qs = qs.filter(date__gte=date_debut)
        if date_fin:
            qs = qs.filter(date__lte=date_fin)
        page = self.paginate_queryset(qs.distinct().order_by("date", "reference"))
        return self.get_paginated_response(JournalEntrySerializer(page, many=True).data)

    @action(detail=False, methods=["get"], url_path="compte-de-resultat")
    def compte_resultat(self, request):
        fy = self._exercice(request)
        return Response(services.compte_de_resultat(request.company, fy))

    @action(detail=False, methods=["get"], url_path="bilan")
    def bilan(self, request):
        fy = self._exercice(request)
        return Response(services.bilan_simplifie(request.company, fy))

    def _exercice(self, request):
        fy_id = request.query_params.get("fiscal_year")
        if fy_id:
            return FiscalYear.objects.filter(company=request.company, pk=fy_id).first()
        from django.utils import timezone

        return FiscalYear.pour_date(request.company, timezone.localdate())
