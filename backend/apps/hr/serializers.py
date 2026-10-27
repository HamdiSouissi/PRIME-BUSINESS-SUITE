from rest_framework import serializers

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


class ContractSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    type_label = serializers.CharField(source="get_contract_type_display", read_only=True)

    class Meta:
        model = Contract
        fields = "__all__"

    def validate(self, attrs):
        """Fait appel à la validation métier du modèle sur les données fusionnées."""
        data = {}
        for field in Contract._meta.get_fields():
            if field.concrete and not field.auto_created and field.name != "id":
                if field.name in attrs:
                    data[field.name] = attrs[field.name]
                elif self.instance is not None:
                    data[field.name] = getattr(self.instance, field.name)
        candidate = Contract(**data)
        candidate.clean()
        return attrs


class EmployeeListSerializer(serializers.ModelSerializer):
    contrat_actif = ContractSerializer(read_only=True)
    manager_name = serializers.CharField(source="manager.full_name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Employee
        fields = (
            "id", "matricule", "first_name", "last_name", "full_name", "position",
            "department", "manager", "manager_name", "hire_date", "status",
            "status_label", "email_pro", "user", "contrat_actif",
        )


class EmployeeDetailSerializer(serializers.ModelSerializer):
    contrats = ContractSerializer(many=True, read_only=True)
    manager_name = serializers.CharField(source="manager.full_name", read_only=True)

    class Meta:
        model = Employee
        fields = "__all__"
        # company est injectée par CompanyScopedViewSet.perform_create, jamais
        # fournie par le client : sinon la validation échoue (400 « Ce champ est
        # obligatoire ») et toute création de salarié est impossible.
        read_only_fields = ("company",)


class ContractAmendmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractAmendment
        fields = "__all__"
        read_only_fields = ("created_by",)


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = "__all__"
        read_only_fields = ("company",)


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    leave_type_label = serializers.CharField(source="leave_type.label", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    decided_by_email = serializers.EmailField(source="decided_by.email", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = "__all__"
        read_only_fields = ("status", "decided_by", "decided_at", "manager_comment", "company")
        extra_kwargs = {"business_days": {"required": False, "allow_null": True}}


class LeaveBalanceSerializer(serializers.ModelSerializer):
    remaining = serializers.ReadOnlyField()
    leave_type_label = serializers.CharField(source="leave_type.label", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = LeaveBalance
        fields = "__all__"
        read_only_fields = ("company",)


class EquipmentItemSerializer(serializers.ModelSerializer):
    is_returned = serializers.ReadOnlyField()
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = EquipmentItem
        fields = "__all__"
        read_only_fields = ("company",)


class TrainingRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = TrainingRecord
        fields = "__all__"
        read_only_fields = ("company",)


class InterviewSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = Interview
        fields = "__all__"
        read_only_fields = ("company",)


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeDocument
        fields = "__all__"
        read_only_fields = ("uploaded_by", "company")

    def get_url(self, obj):
        if obj.file:
            return f"/api/documents/hr/{obj.pk}/telecharger/"
        return None
