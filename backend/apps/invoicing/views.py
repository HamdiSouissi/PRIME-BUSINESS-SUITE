"""API de facturation : clients, fournisseurs, devis, factures, règlements."""

from django.core.files.base import ContentFile
from django.http import FileResponse
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessError
from apps.core.permissions import HasRole, ReadOnlyOrRole, Roles
from apps.core.services_pdf import html_vers_pdf
from apps.core.viewsets import CompanyScopedViewSet

from . import services
from .models import (
    Client,
    EInvoicingConfig,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentSchedule,
    Quote,
    QuoteStatus,
    ReminderLog,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceStatus,
)
from .serializers import (
    ClientSerializer,
    EInvoicingConfigSerializer,
    InvoiceSerializer,
    PaymentScheduleSerializer,
    PaymentSerializer,
    QuoteSerializer,
    ReminderLogSerializer,
    SupplierInvoiceSerializer,
    SupplierSerializer,
)

FACT_ROLES = (Roles.ADMIN, Roles.DIRECTION, Roles.FINANCE, Roles.COMPTABLE, Roles.RH)
COMPTA_ROLES = (Roles.ADMIN, Roles.COMPTABLE, Roles.FINANCE)


class ClientViewSet(CompanyScopedViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*FACT_ROLES))
    filterset_fields = ("is_active",)
    search_fields = ("name", "code", "email")


class SupplierViewSet(CompanyScopedViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*COMPTA_ROLES, Roles.RH, Roles.DIRECTION))
    filterset_fields = ("is_active",)
    search_fields = ("name", "code", "email")


class QuoteViewSet(CompanyScopedViewSet):
    queryset = Quote.objects.select_related("client").prefetch_related("lines").all()
    serializer_class = QuoteSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*FACT_ROLES, Roles.MANAGER))
    filterset_fields = ("status", "client")
    search_fields = ("number", "subject", "client__name")

    def perform_create(self, serializer):
        quote = serializer.save(company=self.request.company)
        lignes = self.request.data.get("lignes", [])
        for idx, data in enumerate(lignes):
            quote.lines.create(
                order=idx,
                description=data.get("description", ""),
                quantity=data.get("quantity", 1),
                unit_price_ht=data.get("unit_price_ht", 0),
                vat_rate=data.get("vat_rate", 20),
            )
        services.calculer_totaux_devis(quote)

    def perform_update(self, serializer):
        quote = self.get_object()
        if quote.status != QuoteStatus.BROUILLON:
            raise BusinessError("Seul un devis brouillon est modifiable.", code="transition_interdite")
        services.calculer_totaux_devis(serializer.save())

    @action(detail=True, methods=["post"], url_path="envoyer")
    def envoyer(self, request, pk=None):
        quote = self.get_object()
        if quote.status != QuoteStatus.BROUILLON:
            raise BusinessError("Devis déjà envoyé.", code="transition_interdite")
        from apps.core.models import Sequence

        services.calculer_totaux_devis(quote)
        quote.number = Sequence.allocate(quote.company, key="quote", prefix="DE",
                                         year=quote.issue_date.year, padding=5)
        quote.status = QuoteStatus.ENVOYE
        quote.save(update_fields=["number", "status", "updated_at"])
        return Response(QuoteSerializer(quote).data)

    @action(detail=True, methods=["post"], url_path="decision")
    def decision(self, request, pk=None):
        quote = self.get_object()
        decision = request.data.get("decision")
        if decision not in {"accepte", "refuse"}:
            raise BusinessError("Décision attendue : accepte | refuse.", code="decision_inconnue")
        if quote.status != QuoteStatus.ENVOYE:
            raise BusinessError("Seul un devis envoyé reçoit une décision.", code="transition_interdite")
        quote.status = QuoteStatus.ACCEPTE if decision == "accepte" else QuoteStatus.REFUSE
        quote.save(update_fields=["status", "updated_at"])
        return Response(QuoteSerializer(quote).data)

    @action(detail=True, methods=["post"], url_path="convertir")
    def convertir(self, request, pk=None):
        """Convertit le devis accepté en facture brouillon."""
        quote = self.get_object()
        invoice = services.convertir_devis(quote)
        return Response(InvoiceSerializer(invoice).data, status=201)


class InvoiceViewSet(CompanyScopedViewSet):
    queryset = Invoice.objects.select_related("client").prefetch_related("lines", "paiements", "relances").all()
    serializer_class = InvoiceSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*FACT_ROLES))
    filterset_fields = ("status", "client", "invoice_type", "issue_date", "due_date")
    search_fields = ("number", "client__name")
    ordering_fields = ("issue_date", "due_date", "total_ttc")

    def perform_create(self, serializer):
        invoice = serializer.save(company=self.request.company, status=InvoiceStatus.BROUILLON)
        lignes = self.request.data.get("lignes")
        if lignes:
            services.remplacer_lignes_invoice(invoice, lignes)

    def perform_update(self, serializer):
        invoice = self.get_object()
        if invoice.status != InvoiceStatus.BROUILLON:
            raise BusinessError(
                "Facture émise : modification interdite. Utilisez un avoir ou une "
                "régularisation comptable.",
                code="facture_gelee",
            )
        serializer.save()
        if "lignes" in self.request.data:
            services.remplacer_lignes_invoice(invoice, self.request.data["lignes"])

    def destroy(self, request, *args, **kwargs):
        invoice = self.get_object()
        if invoice.status != InvoiceStatus.BROUILLON:
            raise BusinessError(
                "Une facture émise ne se supprime pas : créez un avoir d'annulation.",
                code="suppression_interdite",
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="lignes")
    def lignes(self, request, pk=None):
        invoice = self.get_object()
        services.remplacer_lignes_invoice(invoice, request.data.get("lignes", []))
        return Response(InvoiceSerializer(invoice).data)

    @action(detail=True, methods=["post"], url_path="emettre")
    def emettre(self, request, pk=None):
        invoice = self.get_object()
        services.emettre_invoice(invoice)
        return Response(InvoiceSerializer(invoice).data)

    @action(detail=True, methods=["post"], url_path="avoir")
    def avoir(self, request, pk=None):
        invoice = self.get_object()
        avoir = services.creer_avoir(invoice, motif=request.data.get("motif", ""))
        services.emettre_invoice(avoir)
        return Response(InvoiceSerializer(avoir).data, status=201)

    @action(detail=True, methods=["post"], url_path="relance")
    def relance(self, request, pk=None):
        invoice = self.get_object()
        level = int(request.data.get("level", 1))
        reminder = services.relancer_facture(invoice, request.user, level,
                                             request.data.get("note", ""))
        return Response(ReminderLogSerializer(reminder).data, status=201)

    @action(detail=True, methods=["post"], url_path="pdf")
    def pdf(self, request, pk=None):
        """Génère (ou régénère) le PDF de la facture."""
        invoice = self.get_object()
        if invoice.status == InvoiceStatus.BROUILLON:
            raise BusinessError("Émettez la facture avant de générer le PDF.", code="transition_interdite")
        html = render_to_string("invoicing/facture.html", {"invoice": invoice, "company": invoice.company})
        pdf_bytes = html_vers_pdf(html)
        invoice.pdf.save(f"facture-{invoice.number}.pdf", ContentFile(pdf_bytes), save=True)
        return Response({"pdf_url": f"/api/invoicing/invoices/{invoice.pk}/pdf/"})

    @action(detail=True, methods=["get"], url_path="telecharger")
    def telecharger(self, request, pk=None):
        invoice = self.get_object()
        if not invoice.pdf:
            return Response({"detail": "PDF non généré."}, status=404)
        return FileResponse(invoice.pdf.open("rb"), content_type="application/pdf",
                            as_attachment=True, filename=f"{invoice.number}.pdf")

    @action(detail=True, methods=["post"], url_path="comptabiliser",
            permission_classes=[IsAuthenticated, HasRole.of(*COMPTA_ROLES)])
    def comptabiliser(self, request, pk=None):
        """Génère l'écriture comptable de la facture (journal des ventes)."""
        from apps.invoicing import services_accounting

        invoice = self.get_object()
        entry = services_accounting.comptabiliser_facture_client(invoice, request.user)
        return Response({"entry_id": entry.id, "reference": entry.reference})


class SupplierInvoiceViewSet(CompanyScopedViewSet):
    queryset = SupplierInvoice.objects.select_related("supplier", "validated_by").prefetch_related("lines", "paiements").all()
    serializer_class = SupplierInvoiceSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*COMPTA_ROLES, Roles.DIRECTION))
    filterset_fields = ("status", "supplier", "due_date")
    search_fields = ("supplier_reference", "supplier__name", "internal_number")

    def perform_create(self, serializer):
        invoice = serializer.save(company=self.request.company, status=SupplierInvoiceStatus.RECUE)
        sources = self.request.data.get("lignes")
        if sources:
            services.remplacer_lignes_supplier(invoice, sources)

    def perform_update(self, serializer):
        invoice = self.get_object()
        if invoice.status not in {SupplierInvoiceStatus.RECUE, SupplierInvoiceStatus.A_VALIDER}:
            raise BusinessError(
                "Facture fournisseur validée : modification interdite.", code="facture_gelee"
            )
        serializer.save()

    @action(detail=True, methods=["post"], url_path="valider",
            permission_classes=[IsAuthenticated, HasRole.of(*COMPTA_ROLES)])
    def valider(self, request, pk=None):
        """Validation humaine obligatoire avant paiement/comptabilisation."""
        from apps.core.models import Sequence

        invoice = self.get_object()
        if invoice.status in {SupplierInvoiceStatus.VALIDEE, SupplierInvoiceStatus.PAYEE}:
            raise BusinessError("Facture déjà validée.", code="transition_interdite")
        if not invoice.lines.exists():
            services.remplacer_lignes_supplier(invoice, request.data.get("lignes", []))
        invoice.internal_number = invoice.internal_number or Sequence.allocate(
            invoice.company, key="supplier_invoice", prefix="FF",
            year=invoice.invoice_date.year, padding=5,
        )
        invoice.status = SupplierInvoiceStatus.VALIDEE
        invoice.validated_by = request.user
        invoice.save()
        return Response(SupplierInvoiceSerializer(invoice).data)

    @action(detail=True, methods=["post"], url_path="comptabiliser",
            permission_classes=[IsAuthenticated, HasRole.of(*COMPTA_ROLES)])
    def comptabiliser(self, request, pk=None):
        from apps.invoicing import services_accounting

        invoice = self.get_object()
        entry = services_accounting.comptabiliser_facture_fournisseur(invoice, request.user)
        return Response({"entry_id": entry.id, "reference": entry.reference})


class PaymentViewSet(CompanyScopedViewSet):
    queryset = Payment.objects.select_related("invoice", "supplier_invoice").all()
    serializer_class = PaymentSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*COMPTA_ROLES, Roles.DIRECTION))
    filterset_fields = ("invoice", "supplier_invoice", "direction", "method")

    def perform_create(self, serializer):
        data = serializer.validated_data
        services.enregistrer_paiement(
            company=self.request.company,
            invoice=data.get("invoice"),
            supplier_invoice=data.get("supplier_invoice"),
            date=data.get("date") or timezone.localdate(),
            amount=data["amount"],
            method=data.get("method", "virement"),
            reference=data.get("reference", ""),
        )


class PaymentScheduleViewSet(CompanyScopedViewSet):
    queryset = PaymentSchedule.objects.select_related("invoice").all()
    serializer_class = PaymentScheduleSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*FACT_ROLES))
    filterset_fields = ("invoice", "is_paid")
    ordering_fields = ("due_date",)


class EInvoicingConfigViewSet(viewsets.ViewSet):
    """Configuration du partenaire de facturation électronique (singleton)."""

    permission_classes = (IsAuthenticated,)

    def list(self, request):
        config, _ = EInvoicingConfig.objects.get_or_create(company=request.company)
        return Response(EInvoicingConfigSerializer(config).data)

    def partial_update(self, request, pk=None):
        if user := request.user:
            pass
        config, _ = EInvoicingConfig.objects.get_or_create(company=request.company)
        if "api_key" in request.data:
            from apps.core.secrets import chiffrer

            config.api_key_encrypted = chiffrer(request.data["api_key"])
        serializer = EInvoicingConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(EInvoicingConfigSerializer(config).data)
