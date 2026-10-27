from rest_framework import serializers

from .models import Account, EntryLine, FiscalYear, Journal, JournalEntry


class AccountSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_account_type_display", read_only=True)

    class Meta:
        model = Account
        fields = "__all__"
        read_only_fields = ("company",)


class JournalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Journal
        fields = "__all__"
        read_only_fields = ("company",)


class FiscalYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalYear
        fields = "__all__"
        read_only_fields = ("company",)


class EntryLineSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(source="account.number", read_only=True)
    account_label = serializers.CharField(source="account.label", read_only=True)

    class Meta:
        model = EntryLine
        fields = ("id", "account", "account_number", "account_label", "label", "auxiliary", "debit", "credit")


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = EntryLineSerializer(many=True, read_only=True)
    journal_code = serializers.CharField(source="journal.code", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    total_debit = serializers.ReadOnlyField()
    total_credit = serializers.ReadOnlyField()
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    validated_by_email = serializers.EmailField(source="validated_by.email", read_only=True)

    class Meta:
        model = JournalEntry
        fields = "__all__"
        read_only_fields = (
            "company", "reference", "status", "created_by", "validated_by",
            "validated_at", "reverses", "source_model", "source_id", "source_label",
        )
