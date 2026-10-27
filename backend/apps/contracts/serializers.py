from rest_framework import serializers

from .models import DocumentTemplate, GeneratedDocument


class DocumentTemplateSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_template_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    variables = serializers.SerializerMethodField()

    class Meta:
        model = DocumentTemplate
        fields = "__all__"
        read_only_fields = ("company", "validated_by", "validated_at", "supersedes")

    def get_variables(self, obj):
        from .services import variables_requises

        return variables_requises(obj)


class GeneratedDocumentSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedDocument
        fields = "__all__"
        read_only_fields = ("company", "content_snapshot", "context_data", "validated_by",
                            "validated_at", "created_by", "ai_draft")

    def get_pdf_url(self, obj):
        return f"/api/contracts/documents/{obj.pk}/telecharger/" if obj.pdf else None
