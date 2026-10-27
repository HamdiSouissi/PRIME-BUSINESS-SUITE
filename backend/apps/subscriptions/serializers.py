from rest_framework import serializers

from .models import Subscription, SubscriptionInvoice


class SubscriptionSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    periodicity_label = serializers.CharField(source="get_periodicity_display", read_only=True)
    montant_ht = serializers.ReadOnlyField(source="montant_par_periode_ht")
    montant_ttc = serializers.ReadOnlyField(source="montant_par_periode_ttc")
    mrr = serializers.ReadOnlyField(source="mrr_contribution")

    class Meta:
        model = Subscription
        fields = "__all__"
        read_only_fields = ("company", "history", "created_by", "canceled_at")
        extra_kwargs = {"next_billing_date": {"required": True}}


class SubscriptionInvoiceSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)
    subscription_label = serializers.CharField(source="subscription.label", read_only=True)

    class Meta:
        model = SubscriptionInvoice
        fields = "__all__"
        read_only_fields = ("company",)
