from rest_framework import serializers

from .models import (
    ContributionRule,
    DSNExport,
    Payslip,
    PayslipLine,
    PayrollParameterSet,
    PayrollRun,
)


class ContributionRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContributionRule
        fields = "__all__"
        read_only_fields = ("parameter_set",)


class PayrollParameterSetSerializer(serializers.ModelSerializer):
    rules = ContributionRuleSerializer(many=True, read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    verified_by_email = serializers.EmailField(source="verified_by.email", read_only=True)
    rules_count = serializers.IntegerField(source="rules.count", read_only=True)

    class Meta:
        model = PayrollParameterSet
        fields = "__all__"
        read_only_fields = ("company", "verified_by", "verified_at")


class PayrollRunSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    bulletins_count = serializers.IntegerField(source="payslips.count", read_only=True)
    masse_brute = serializers.SerializerMethodField()
    masse_net = serializers.SerializerMethodField()
    cout_total = serializers.SerializerMethodField()

    class Meta:
        model = PayrollRun
        fields = "__all__"
        read_only_fields = ("company", "started_by", "validated_by", "validated_at", "closed_at", "history", "status")

    def _sum(self, obj, field):
        from django.db.models import Sum

        return obj.payslips.aggregate(total=Sum(field))["total"]

    def get_masse_brute(self, obj):
        return self._sum(obj, "brut")

    def get_masse_net(self, obj):
        return self._sum(obj, "net_a_payer")

    def get_cout_total(self, obj):
        return self._sum(obj, "cout_employeur")


class PayslipLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayslipLine
        fields = "__all__"


class PayslipListSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    period = serializers.SerializerMethodField()

    class Meta:
        model = Payslip
        fields = (
            "id", "number", "employee", "employee_name", "run", "period", "status",
            "status_label", "brut", "net_imposable", "net_a_payer", "cout_employeur",
            "provisional", "published_to_employee", "created_at",
        )

    def get_period(self, obj):
        return f"{obj.run.month:02d}/{obj.run.year}"


class PayslipDetailSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    lines = PayslipLineSerializer(many=True, read_only=True)
    period = serializers.SerializerMethodField()
    pdf_url = serializers.SerializerMethodField()
    parameter_set_label = serializers.CharField(source="parameter_set.label", read_only=True)

    class Meta:
        model = Payslip
        fields = "__all__"
        # Injecté par le ViewSet/les tâches de paie ; jamais fourni par le client.
        read_only_fields = ("company",)

    def get_period(self, obj):
        return f"{obj.run.month:02d}/{obj.run.year}"

    def get_pdf_url(self, obj):
        if obj.pdf:
            return f"/api/payroll/payslips/{obj.pk}/pdf/"
        return None


class DSNExportSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = DSNExport
        fields = "__all__"
        read_only_fields = ("company", "generated_by", "status", "file")


class PayslipInputsSerializer(serializers.Serializer):
    """Saisie des variables mensuelles d'un bulletin."""

    primes = serializers.ListField(child=serializers.DictField(), required=False)
    retenues = serializers.ListField(child=serializers.DictField(), required=False)
    heures_sup = serializers.ListField(child=serializers.DictField(), required=False)
    avantages_nature = serializers.ListField(child=serializers.DictField(), required=False)
    remboursements = serializers.ListField(child=serializers.DictField(), required=False)
    taux_pas = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
