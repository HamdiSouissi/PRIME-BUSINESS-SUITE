from rest_framework import serializers

from .models import Company


class CompanySerializer(serializers.ModelSerializer):
    """Sérialiseur complet de la configuration de l'entreprise."""

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "legal_form",
            "address",
            "postal_code",
            "city",
            "country",
            "email",
            "phone",
            "website",
            "siren",
            "siret",
            "vat_number",
            "rcs_city",
            "rcs_number",
            "naf_code",
            "share_capital",
            "currency",
            "vat_regime",
            "fiscal_year_start_month",
            "bank_iban",
            "bank_bic",
            "bank_name",
            "logo",
            "collective_agreement",
            "collective_agreement_idcc",
            "work_time_weekly_hours",
            "accountant_name",
            "accountant_email",
            "accountant_phone",
            "headcount",
            "invoice_footer",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_at", "updated_at")


class CompanySummarySerializer(serializers.ModelSerializer):
    """Version allégée exposée aux utilisateurs authentifiés."""

    class Meta:
        model = Company
        fields = ("id", "name", "legal_form", "logo", "currency", "city")
