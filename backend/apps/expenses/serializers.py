from rest_framework import serializers

from .models import ExpenseCategory, ExpenseLine, ExpenseReport


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = "__all__"
        read_only_fields = ("company",)


class ExpenseLineSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="category.label", read_only=True)
    receipt_url = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseLine
        fields = "__all__"
        read_only_fields = ("company", "over_policy", "duplicate_suspect")

    def get_receipt_url(self, obj):
        return f"/api/expenses/lignes/{obj.pk}/justificatif/" if obj.receipt else None


class ExpenseReportSerializer(serializers.ModelSerializer):
    lines = ExpenseLineSerializer(many=True, read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    decided_by_email = serializers.EmailField(source="decided_by.email", read_only=True)

    class Meta:
        model = ExpenseReport
        fields = "__all__"
        read_only_fields = ("company", "status", "total_amount", "submitted_at",
                            "decided_by", "decided_at", "reimbursed_at", "accounting_entry")
