"""API des notes de frais."""

from django.http import FileResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessError
from apps.core.permissions import HasRole, ReadOnlyOrRole, Roles, user_role
from apps.core.viewsets import CompanyScopedViewSet

from . import services
from .models import ExpenseCategory, ExpenseLine, ExpenseReport, ExpenseReportStatus
from .serializers import ExpenseCategorySerializer, ExpenseLineSerializer, ExpenseReportSerializer

FRAIS_ROLES = (Roles.ADMIN, Roles.RH, Roles.COMPTABLE, Roles.FINANCE)
DECIDEURS = (Roles.ADMIN, Roles.RH, Roles.MANAGER)


class ExpenseCategoryViewSet(CompanyScopedViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*FRAIS_ROLES))


class ExpenseReportViewSet(CompanyScopedViewSet):
    queryset = ExpenseReport.objects.select_related("employee", "decided_by").prefetch_related("lines__category").all()
    serializer_class = ExpenseReportSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("status", "employee")
    search_fields = ("title", "employee__last_name", "employee__first_name")

    def get_queryset(self):
        qs = super().get_queryset()
        if user_role(self.request) == Roles.SALARIE:
            profile = getattr(self.request.user, "employee_profile", None)
            return qs.filter(employee=profile) if profile else qs.none()
        return qs

    def perform_create(self, serializer):
        employee = serializer.validated_data["employee"]
        if user_role(self.request) == Roles.SALARIE:
            profile = getattr(self.request.user, "employee_profile", None)
            if profile is None or employee.id != profile.id:
                raise BusinessError("Un salarié crée ses propres notes de frais.", code="hors_perimetre")
        serializer.save(company=self.request.company, status=ExpenseReportStatus.BROUILLON)

    def perform_update(self, serializer):
        report = self.get_object()
        if report.status != ExpenseReportStatus.BROUILLON:
            raise BusinessError("Seule une note brouillon est modifiable.", code="transition_interdite")
        serializer.save()

    @action(detail=True, methods=["post"], url_path="soumettre")
    def soumettre(self, request, pk=None):
        report = self.get_object()
        if user_role(request) == Roles.SALARIE and report.employee.user_id != request.user.id:
            raise BusinessError("Hors périmètre.", code="hors_perimetre")
        services.soumettre(report)
        return Response(ExpenseReportSerializer(report).data)

    @action(detail=True, methods=["post"], url_path="decision",
            permission_classes=[IsAuthenticated, HasRole.of(*DECIDEURS)])
    def decision(self, request, pk=None):
        report = self.get_object()
        services.decider(report, request.data.get("decision", ""),
                         request.data.get("commentaire", ""), request.user)
        return Response(ExpenseReportSerializer(report).data)

    @action(detail=True, methods=["post"], url_path="remboursee",
            permission_classes=[IsAuthenticated, HasRole.of(*FRAIS_ROLES)])
    def remboursee(self, request, pk=None):
        report = self.get_object()
        services.marquer_remboursee(report)
        return Response(ExpenseReportSerializer(report).data)

    @action(detail=True, methods=["post"], url_path="comptabiliser",
            permission_classes=[IsAuthenticated, HasRole.of(Roles.ADMIN, Roles.COMPTABLE)])
    def comptabiliser(self, request, pk=None):
        """Comptabilise la note validée en OD (charge 6xx / personnels 421)."""
        from django.utils import timezone as tz

        from apps.accounting.services import creer_ecriture

        report = self.get_object()
        if report.status != ExpenseReportStatus.VALIDEE:
            raise BusinessError("Seule une note validée est comptabilisable.", code="transition_interdite")
        if report.accounting_entry_id:
            raise BusinessError("Note déjà comptabilisée.", code="deja_comptabilisee")
        lignes = []
        for line in report.lines.select_related("category"):
            ht = line.amount_ttc - line.vat_amount
            if ht > 0:
                lignes.append({
                    "account": line.category.expense_account or "625100",
                    "label": f"NDF {report.title} — {line.description or line.category.label}",
                    "debit": ht,
                    "credit": 0,
                })
            if line.vat_amount and line.category.vat_recoverable:
                lignes.append({
                    "account": "445660",
                    "label": f"TVA récupérable NDF {report.title}",
                    "debit": line.vat_amount,
                    "credit": 0,
                })
        lignes.append({
            "account": "421000",
            "label": f"Remboursement NDF {report.employee.full_name} — {report.title}",
            "debit": 0,
            "credit": report.total_amount,
        })
        date_ecriture = report.submitted_at.date() if report.submitted_at else tz.localdate()
        entry = creer_ecriture(
            report.company, "OD", date_ecriture,
            f"Note de frais {report.title} — {report.employee.full_name}",
            lignes, user=request.user, valider=True,
            source=("expenses.ExpenseReport", str(report.id), report.title),
        )
        report.accounting_entry = entry
        report.status = ExpenseReportStatus.COMPTABILISEE
        report.save(update_fields=["accounting_entry", "status", "updated_at"])
        return Response({"entry_id": entry.id, "reference": entry.reference})


class ExpenseLineViewSet(CompanyScopedViewSet):
    queryset = ExpenseLine.objects.select_related("report__employee", "category").all()
    serializer_class = ExpenseLineSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("report", "category", "over_policy", "duplicate_suspect")

    def perform_create(self, serializer):
        report = serializer.validated_data["report"]
        if report.status != ExpenseReportStatus.BROUILLON:
            raise BusinessError("Note figée : ajout impossible.", code="transition_interdite")
        line = serializer.save(company=self.request.company)
        services.appliquer_controles(line)
        services.recalculer_total(report)

    def perform_update(self, serializer):
        line = self.get_object()
        if line.report.status != ExpenseReportStatus.BROUILLON:
            raise BusinessError("Note figée : modification impossible.", code="transition_interdite")
        line = serializer.save()
        services.appliquer_controles(line)
        services.recalculer_total(line.report)

    def perform_destroy(self, instance):
        report = instance.report
        if report.status != ExpenseReportStatus.BROUILLON:
            raise BusinessError("Note figée : suppression impossible.", code="transition_interdite")
        super().perform_destroy(instance)
        services.recalculer_total(report)

    @action(detail=True, methods=["get"], url_path="justificatif")
    def justificatif(self, request, pk=None):
        line = self.get_object()
        if not line.receipt:
            return Response({"detail": "Pas de justificatif."}, status=404)
        return FileResponse(line.receipt.open("rb"), as_attachment=True,
                            filename=f"justificatif-{line.id}")
