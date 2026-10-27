from rest_framework import serializers

from .models import AIProvider, AIUsageLog, FeatureRouting


class AIProviderSerializer(serializers.ModelSerializer):
    """La clé API chiffrée n'est JAMAIS sérialisée — seulement sa présence."""

    api_key_defined = serializers.SerializerMethodField()
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = AIProvider
        exclude = ("api_key_encrypted",)
        read_only_fields = ("company", "last_status", "last_checked_at", "last_error",
                            "available_models")

    def get_api_key_defined(self, obj):
        return bool(obj.api_key_encrypted)


class AIProviderUpdateSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True,
                                    help_text="Écrite uniquement ; jamais relue.")

    class Meta:
        model = AIProvider
        fields = ("label", "kind", "base_url", "default_model", "is_enabled",
                  "generation_params", "timeout_seconds", "api_key", "billing_info")


class FeatureRoutingSerializer(serializers.ModelSerializer):
    provider_label = serializers.CharField(source="provider.label", read_only=True)
    feature_label = serializers.CharField(source="get_feature_display", read_only=True)

    class Meta:
        model = FeatureRouting
        fields = "__all__"
        read_only_fields = ("company",)


class AIUsageLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = AIUsageLog
        fields = "__all__"
