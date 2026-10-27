from rest_framework import serializers

from .models import (
    Client,
    EInvoicingConfig,
    Invoice,
    InvoiceLine,
    Payment,
    PaymentSchedule,
    Quote,
    QuoteLine,
    ReminderLog,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceLine,
)


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = "__all__"
        read_only_fields = ("company",)


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = "__all__"
        read_only_fields = ("company",)


class QuoteLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteLine
        fields = ("id", "order", "description", "quantity", "unit_price_ht", "vat_rate")


class QuoteSerializer(serializers.ModelSerializer):
    lines = QuoteLineSerializer(many=True, read_only=True)
    client_name = serializers.CharField(source="client.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    lignes = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)

    class Meta:
        model = Quote
        fields = "__all__"
        read_only_fields = ("company", "number", "total_ht", "total_vat", "total_ttc")


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ("id", "order", "description", "quantity", "unit_price_ht", "vat_rate", "total_ht", "total_vat")


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    client_name = serializers.CharField(source="client.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    type_label = serializers.CharField(source="get_invoice_type_display", read_only=True)
    einvoice_status_label = serializers.CharField(source="get_einvoice_status_display", read_only=True)
    reste_a_payer = serializers.ReadOnlyField()
    pdf_url = serializers.SerializerMethodField()
    lignes = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)

    class Meta:
        model = Invoice
        fields = "__all__"
        read_only_fields = (
            "company", "number", "status", "total_ht", "total_vat", "total_ttc",
            "amount_paid", "pdf", "accounting_entry", "einvoice_status",
            "einvoice_platform_id", "einvoice_proof",
        )

    def get_pdf_url(self, obj):
        return f"/api/invoicing/invoices/{obj.pk}/pdf/" if obj.pdf else None


class SupplierInvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierInvoiceLine
        fields = ("id", "order", "description", "quantity", "unit_price_ht", "vat_rate", "total_ht", "total_vat")


class SupplierInvoiceSerializer(serializers.ModelSerializer):
    lines = SupplierInvoiceLineSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    reste_a_payer = serializers.ReadOnlyField()
    lignes = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)

    class Meta:
        model = SupplierInvoice
        fields = "__all__"
        read_only_fields = ("company", "internal_number", "status", "total_ht", "total_vat",
                            "total_ttc", "amount_paid", "accounting_entry", "validated_by")


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)
    supplier_invoice_ref = serializers.CharField(source="supplier_invoice.supplier_reference", read_only=True)

    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ("company", "direction")


class PaymentScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentSchedule
        fields = "__all__"
        read_only_fields = ("company",)


class ReminderLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReminderLog
        fields = "__all__"
        read_only_fields = ("company", "sent_by", "sent_at")


class EInvoicingConfigSerializer(serializers.ModelSerializer):
    """La clé API n'est jamais exposée : uniquement « définie ou non »."""

    api_key_defined = serializers.SerializerMethodField()

    class Meta:
        model = EInvoicingConfig
        exclude = ("api_key_encrypted",)
        read_only_fields = ("company", "last_sync_at")

    def get_api_key_defined(self, obj):
        return bool(obj.api_key_encrypted)
