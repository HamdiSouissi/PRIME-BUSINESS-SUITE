from rest_framework import serializers

from .models import (
    Associate,
    CapitalMovement,
    CurrentAccountEntry,
    DistributionDecision,
    DividendPayment,
)


class AssociateSerializer(serializers.ModelSerializer):
    pct_capital = serializers.ReadOnlyField()

    class Meta:
        model = Associate
        fields = "__all__"
        read_only_fields = ("company",)


class CapitalMovementSerializer(serializers.ModelSerializer):
    associate_name = serializers.SerializerMethodField()

    class Meta:
        model = CapitalMovement
        fields = "__all__"
        read_only_fields = ("company",)

    def get_associate_name(self, obj):
        return str(obj.associate)


class CurrentAccountEntrySerializer(serializers.ModelSerializer):
    associate_name = serializers.SerializerMethodField()

    class Meta:
        model = CurrentAccountEntry
        fields = "__all__"
        read_only_fields = ("company", "accounting_entry")

    def get_associate_name(self, obj):
        return str(obj.associate)


class DistributionDecisionSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    paiements_count = serializers.IntegerField(source="paiements.count", read_only=True)
    decided_by_email = serializers.EmailField(source="decided_by.email", read_only=True)

    class Meta:
        model = DistributionDecision
        fields = "__all__"
        read_only_fields = ("company", "status", "decided_by", "somme_distribuable")


class DividendPaymentSerializer(serializers.ModelSerializer):
    associate_name = serializers.SerializerMethodField()

    class Meta:
        model = DividendPayment
        fields = "__all__"
        read_only_fields = ("company", "paid_by", "gross_amount", "withholding_amount", "net_amount")

    def get_associate_name(self, obj):
        return str(obj.associate)
