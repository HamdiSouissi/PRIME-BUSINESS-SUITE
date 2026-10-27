"""API des modèles de documents et des documents générés."""

from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessError
from apps.core.permissions import HasRole, ReadOnlyOrRole, Roles
from apps.core.viewsets import CompanyScopedViewSet

from . import services
from .models import DocumentTemplate, GeneratedDocument, TemplateStatus
from .serializers import DocumentTemplateSerializer, GeneratedDocumentSerializer

DOC_ROLES = (Roles.ADMIN, Roles.DIRECTION, Roles.RH, Roles.COMPTABLE, Roles.FINANCE)


class DocumentTemplateViewSet(CompanyScopedViewSet):
    queryset = DocumentTemplate.objects.all()
    serializer_class = DocumentTemplateSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*DOC_ROLES))
    filterset_fields = ("template_type", "status")
    search_fields = ("name",)

    @action(detail=True, methods=["post"], url_path="valider",
            permission_classes=[IsAuthenticated, HasRole.of(Roles.ADMIN, Roles.DIRECTION)])
    def valider(self, request, pk=None):
        """Validation juridique du modèle (note de relecture obligatoire)."""
        template = self.get_object()
        note = request.data.get("note", "").strip()
        if not note:
            raise BusinessError(
                "Une note de validation juridique est obligatoire.", code="note_requise"
            )
        template.status = TemplateStatus.VALIDE
        template.validated_by = request.user
        template.validated_at = timezone.now()
        template.legal_review_note = note
        template.save()
        return Response(DocumentTemplateSerializer(template).data)

    @action(detail=True, methods=["post"], url_path="nouvelle-version")
    def nouvelle_version(self, request, pk=None):
        """Crée une nouvelle version du modèle (l'ancienne est archivée)."""
        template = self.get_object()
        nouvelle = DocumentTemplate.objects.create(
            company=template.company,
            template_type=template.template_type,
            name=template.name,
            version=template.version + 1,
            content=request.data.get("content", template.content),
            status=TemplateStatus.BROUILLON,
            supersedes=template,
        )
        template.status = TemplateStatus.ARCHIVE
        template.save(update_fields=["status", "updated_at"])
        return Response(DocumentTemplateSerializer(nouvelle).data, status=201)


class GeneratedDocumentViewSet(CompanyScopedViewSet):
    queryset = GeneratedDocument.objects.select_related("template", "target_employee", "target_client").all()
    serializer_class = GeneratedDocumentSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*DOC_ROLES, Roles.MANAGER))
    filterset_fields = ("status", "template__template_type", "target_employee", "target_client")
    search_fields = ("label",)

    @action(detail=False, methods=["post"], url_path="generer")
    def generer(self, request):
        """Génère un document depuis un modèle validé + contexte JSON."""
        template_id = request.data.get("template")
        contexte = request.data.get("contexte", {})
        template = DocumentTemplate.objects.filter(company=request.company, pk=template_id).first()
        if template is None:
            raise BusinessError("Modèle introuvable.", code="modele_inconnu")
        document = services.generer_document(
            template, contexte, request.user, label=request.data.get("label", ""),
            target_employee_id=request.data.get("target_employee") or None,
            target_client_id=request.data.get("target_client") or None,
            ai_draft=bool(request.data.get("ai_draft", False)),
        )
        return Response(GeneratedDocumentSerializer(document).data, status=201)

    @action(detail=True, methods=["post"], url_path="valider")
    def valider(self, request, pk=None):
        document = services.valider_document(self.get_object(), request.user)
        return Response(GeneratedDocumentSerializer(document).data)

    @action(detail=True, methods=["post"], url_path="pdf")
    def pdf(self, request, pk=None):
        document = services.generer_pdf(self.get_object())
        return Response(GeneratedDocumentSerializer(document).data)

    @action(detail=True, methods=["get"], url_path="telecharger")
    def telecharger(self, request, pk=None):
        document = self.get_object()
        if not document.pdf:
            raise BusinessError("PDF non généré.", code="pas_de_pdf")
        return FileResponse(document.pdf.open("rb"), content_type="application/pdf",
                            as_attachment=True, filename=f"{document.label[:60]}.pdf")

    @action(detail=True, methods=["get"], url_path="docx")
    def docx(self, request, pk=None):
        document = self.get_object()
        contenu = services.generer_docx(document)
        response = HttpResponse(
            contenu,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        response["Content-Disposition"] = f'attachment; filename="{document.label[:60]}.docx"'
        return response
