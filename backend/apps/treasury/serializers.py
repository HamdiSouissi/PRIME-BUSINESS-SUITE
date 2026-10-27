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

    def create(self, validated_data):
        # L'empreinte de déduplication est normalement produite par l'import CSV ;
        # pour une saisie directe via l'API, on la calcule ici pour éviter une
        # violation NOT NULL tout en conservant l'unicité (compte, empreinte).
        account = validated_data["bank_account"]
        empreinte = BankTransaction.compute_hash(
            account.id, validated_data["date"],
            validated_data["label"], validated_data["amount"],
        )
        if BankTransaction.objects.filter(bank_account=account, dedupe_hash=empreinte).exists():
            raise serializers.ValidationError(
                "Cette opération existe déjà pour ce compte (doublon détecté)."
            )
        validated_data["dedupe_hash"] = empreinte
        return super().create(validated_data)

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
