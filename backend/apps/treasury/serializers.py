from rest_framework import serializers

from .models import BankAccount, BankTransaction, CashEvent


class BankAccountSerializer(serializers.ModelSerializer):
    solde_bancaire = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = "__all__"
        read_only_fields = ("company",)

    def get_solde_bancaire(self, obj):
        from .services import solde_bancaire

        return solde_bancaire(obj)


class BankTransactionSerializer(serializers.ModelSerializer):
    bank_account_label = serializers.CharField(source="bank_account.label", read_only=True)
    payment_label = serializers.SerializerMethodField()

    class Meta:
        model = BankTransaction
        fields = "__all__"
        read_only_fields = ("company", "dedupe_hash", "reconciled", "reconciled_by", "reconciled_at")

    def get_payment_label(self, obj):
        if obj.payment:
            if obj.payment.invoice:
                return f"Règlement {obj.payment.invoice.number}"
            if obj.payment.supplier_invoice:
                return f"Règlement fournisseur {obj.payment.supplier_invoice.internal_number}"
        return ""


class CashEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashEvent
        fields = "__all__"
        read_only_fields = ("company",)
