from rest_framework import serializers

from .models import ObligationDefinition, ObligationInstance


class ObligationDefinitionSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    periodicity_label = serializers.CharField(source="get_periodicity_display", read_only=True)

    class Meta:
        model = ObligationDefinition
        fields = "__all__"


class ObligationInstanceSerializer(serializers.ModelSerializer):
    definition_label = serializers.CharField(source="definition.label", read_only=True)
    category = serializers.CharField(source="definition.category", read_only=True)
    source = serializers.URLField(source="definition.source_url", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    days_late = serializers.ReadOnlyField()

    class Meta:
        model = ObligationInstance
        fields = "__all__"
        read_only_fields = ("company", "completed_by", "completed_at")
