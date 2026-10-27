"""API RH : dossiers salariés, contrats, absences et portail salarié."""

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessError
from apps.core.permissions import HasRole, ReadOnlyOrRole, Roles, user_role
from apps.core.viewsets import CompanyScopedViewSet

from . import services
from .models import (
    Contract,
    ContractAmendment,
    Employee,
    EmployeeDocument,
    EquipmentItem,
    Interview,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    TrainingRecord,
)
from .serializers import (
    ContractAmendmentSerializer,
    ContractSerializer,
    EmployeeDetailSerializer,
    EmployeeDocumentSerializer,
    EmployeeListSerializer,
    EquipmentItemSerializer,
    InterviewSerializer,
    LeaveBalanceSerializer,
    LeaveRequestSerializer,
    LeaveTypeSerializer,
    TrainingRecordSerializer,
)

RH_ROLES = (Roles.ADMIN, Roles.DIRECTION, Roles.RH)
RH_PAIE_ROLES = (Roles.ADMIN, Roles.RH, Roles.PAIE)


class EmployeeViewSet(CompanyScopedViewSet):
    queryset = Employee.objects.select_related("manager", "user").all()
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*RH_ROLES))
    filterset_fields = ("status", "department")
    search_fields = ("first_name", "last_name", "matricule", "position", "email_pro")

    def get_serializer_class(self):
        if self.action == "list":
            return EmployeeListSerializer
        return EmployeeDetailSerializer

    @action(detail=True, methods=["post"], url_path="cloturer-dossier",
            permission_classes=[IsAuthenticated, HasRole.of(*RH_ROLES)])
    def cloturer(self, request, pk=None):
        """Clôture le dossier d'un salarié sorti (traçabilité conservée)."""
        employee = self.get_object()
        exit_date = request.data.get("exit_date") or timezone.localdate()
        employee.status = "sorti"
        employee.exit_date = exit_date
        employee.save(update_fields=["status", "exit_date", "updated_at"])
        return Response(EmployeeDetailSerializer(employee).data)


class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.select_related("employee", "employee__company").all()
    serializer_class = ContractSerializer
    permission_classes = (IsAuthenticated, HasRole.of(*RH_PAIE_ROLES))
    filterset_fields = ("employee", "contract_type")

    def get_queryset(self):
        qs = super().get_queryset()
        company = getattr(self.request, "company", None)
        return qs.filter(employee__company=company) if company else qs.none()

    def perform_create(self, serializer):
        company = getattr(self.request, "company", None)
        employee = serializer.validated_data.get("employee")
        if company and employee.company_id != company.id:
            raise BusinessError("Salarié hors de l'entreprise active.", code="hors_perimetre")
        serializer.save()

    @action(detail=True, methods=["post"], url_path="avenants")
    def add_amendment(self, request, pk=None):
        """Ajoute un avenant et applique les modifications au contrat."""
        contract = self.get_object()
        changes = request.data.get("changes", {}) or {}
        before = {k: getattr(contract, k, None) for k in changes}
        serialized_changes = {}
        for key, new_value in changes.items():
            if not hasattr(contract, key):
                raise BusinessError(f"Champ inconnu : {key}", code="champ_inconnu")
            serialized_changes[key] = {
                "avant": str(before[key]),
                "apres": str(new_value),
            }
            setattr(contract, key, new_value)
        contract.full_clean()
        contract.save()
        amendment = ContractAmendment.objects.create(
            contract=contract,
            effective_date=request.data.get("effective_date") or timezone.localdate(),
            reason=request.data.get("reason", "Modification contractuelle"),
            changes=serialized_changes,
            created_by=request.user,
        )
        return Response(ContractAmendmentSerializer(amendment).data, status=201)


class LeaveTypeViewSet(CompanyScopedViewSet):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*RH_ROLES))


class LeaveRequestViewSet(CompanyScopedViewSet):
    """Demandes de congés : dépôt, validation, refus, annulation."""

    queryset = LeaveRequest.objects.select_related("employee", "leave_type", "decided_by").all()
    serializer_class = LeaveRequestSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("employee", "leave_type", "status", "start_date")
    ordering_fields = ("start_date", "created_at")

    def get_queryset(self):
        qs = super().get_queryset()
        role = user_role(self.request)
        if role == Roles.SALARIE:
            profile = getattr(self.request.user, "employee_profile", None)
            if profile is None:
                return qs.none()
            return qs.filter(employee=profile)
        return qs

    def perform_create(self, serializer):
        company = getattr(self.request, "company", None)
        if company is None:
            raise BusinessError("Aucune entreprise active.", code="pas_d_entreprise")
        employee = serializer.validated_data["employee"]
        role = user_role(self.request)
        if role == Roles.SALARIE:
            profile = getattr(self.request.user, "employee_profile", None)
            if profile is None or employee.id != profile.id:
                raise BusinessError(
                    "Un salarié ne peut déposer que ses propres demandes.",
                    code="hors_perimetre",
                )
        start = serializer.validated_data["start_date"]
        end = serializer.validated_data["end_date"]
        business_days = serializer.validated_data.get("business_days") or services.jours_ouvres(
            start,
            end,
            serializer.validated_data.get("half_day_start", False),
            serializer.validated_data.get("half_day_end", False),
        )
        serializer.save(company=company, business_days=business_days, status="soumise")

    def perform_update(self, serializer):
        role = user_role(self.request)
        obj = self.get_object()
        if obj.status != "soumise":
            raise BusinessError(
                "Une demande déjà traitée n'est plus modifiable.", code="transition_interdite"
            )
        if role == Roles.SALARIE:
            profile = getattr(self.request.user, "employee_profile", None)
            if profile is None or obj.employee_id != profile.id:
                raise BusinessError("Hors périmètre.", code="hors_perimetre")
        serializer.save()

    @action(detail=True, methods=["post"], url_path="decision",
            permission_classes=[IsAuthenticated, HasRole.of(Roles.ADMIN, Roles.RH, Roles.MANAGER)])
    def decision(self, request, pk=None):
        """Décision du responsable : `decision` = validee | refusee."""
        obj = self.get_object()
        decision = request.data.get("decision")
        commentaire = request.data.get("commentaire", "")
        services.decider_absence(obj, decision, commentaire, request.user)
        return Response(LeaveRequestSerializer(obj).data)

    @action(detail=True, methods=["post"], url_path="annuler")
    def annuler(self, request, pk=None):
        obj = self.get_object()
        role = user_role(request)
        if role == Roles.SALARIE and obj.employee.user_id != request.user.id:
            raise BusinessError("Hors périmètre.", code="hors_perimetre")
        services.annuler_absence(obj, request.user)
        return Response(LeaveRequestSerializer(obj).data)


class LeaveBalanceViewSet(CompanyScopedViewSet):
    queryset = LeaveBalance.objects.select_related("employee", "leave_type").all()
    serializer_class = LeaveBalanceSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*RH_ROLES))
    filterset_fields = ("employee", "year", "leave_type")


class EquipmentItemViewSet(CompanyScopedViewSet):
    queryset = EquipmentItem.objects.select_related("employee").all()
    serializer_class = EquipmentItemSerializer
    permission_classes = (IsAuthenticated, HasRole.of(*RH_ROLES))
    filterset_fields = ("employee",)


class TrainingRecordViewSet(CompanyScopedViewSet):
    queryset = TrainingRecord.objects.select_related("employee").all()
    serializer_class = TrainingRecordSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*RH_ROLES))
    filterset_fields = ("employee",)


class InterviewViewSet(CompanyScopedViewSet):
    queryset = Interview.objects.select_related("employee").all()
    serializer_class = InterviewSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*RH_ROLES))
    filterset_fields = ("employee", "interview_type")


class EmployeeDocumentViewSet(CompanyScopedViewSet):
    queryset = EmployeeDocument.objects.select_related("employee").all()
    serializer_class = EmployeeDocumentSerializer
    permission_classes = (IsAuthenticated, HasRole.of(*RH_ROLES))
    filterset_fields = ("employee", "category")

    def perform_create(self, serializer):
        serializer.save(company=getattr(self.request, "company", None), uploaded_by=self.request.user)
