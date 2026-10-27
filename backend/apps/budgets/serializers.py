from rest_framework import serializers

from .models import Budget, BudgetLine


class BudgetLineSerializer(serializers.ModelSerializer):
    total_annuel = serializers.ReadOnlyField()
    nature_label = serializers.CharField(source="get_nature_display", read_only=True)

    class Meta:
        model = BudgetLine
        fields = "__all__"
        read_only_fields = ("company",)


class BudgetSerializer(serializers.ModelSerializer):
    lines = BudgetLineSerializer(many=True, read_only=True)

    class Meta:
        model = Budget
        fields = "__all__"
        read_only_fields = ("company",)
