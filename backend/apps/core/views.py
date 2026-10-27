"""Endpoints transverses : santé, tableau de bord, documents, audit."""

from decimal import Decimal

from django.http import FileResponse, HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import AuditLog
from apps.core.permissions import HasRole, Roles, user_role


@api_view(["GET"])
@permission_classes([])
def health(request):
    """Sonde de santé publique (docker / load-balancer)."""
    from django.db import connection

    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False
    return JsonResponse({"status": "ok" if db_ok else "degraded", "database": db_ok})


class DashboardView(APIView):
    """Tableau de bord agrégé : chaque carte affiche sa définition."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        company = request.company
        if company is None:
            return Response({"detail": "Aucune entreprise active."}, status=400)

        from apps.invoicing.models import Invoice, InvoiceStatus, SupplierInvoice, SupplierInvoiceStatus
        from apps.treasury import services as treasury_services
        from apps.treasury.models import BankAccount
        from apps.subscriptions.services import indicateurs as mrr_indicateurs
        from apps.hr.models import Employee, LeaveRequest
        from apps.expenses.models import ExpenseReport, ExpenseReportStatus
        from apps.compliance.services import tableau_de_bord as conformite_bord

        today = timezone.localdate()

        comptes = BankAccount.objects.filter(company=company, is_active=True)
        solde_bancaire_total = sum(treasury_services.solde_bancaire(c) for c in comptes)

        factures_echues = Invoice.objects.filter(
            company=company,
            status__in=(InvoiceStatus.EMISE, InvoiceStatus.EN_RETARD, InvoiceStatus.PARTIELLEMENT_PAYEE),
            due_date__lt=today,
        )
        encours_clients = Invoice.objects.filter(
            company=company,
            status__in=(InvoiceStatus.EMISE, InvoiceStatus.EN_RETARD, InvoiceStatus.PARTIELLEMENT_PAYEE),
        )
        a_payer_fournisseurs = SupplierInvoice.objects.filter(
            company=company,
            status__in=(SupplierInvoiceStatus.VALIDEE, SupplierInvoiceStatus.PARTIELLEMENT_PAYEE,
                        SupplierInvoiceStatus.EN_RETARD),
        )

        absences_attente = LeaveRequest.objects.filter(company=company, status="soumise").count()
        frais_attente = ExpenseReport.objects.filter(
            company=company, status=ExpenseReportStatus.SOUMISE
        ).count()

        try:
            conformite = conformite_bord(company)
        except Exception:
            conformite = {"compteurs": {"a_faire": 0, "depassees": 0}, "a_faire": []}

        from django.db.models import Sum

        return Response(
            {
                "entreprise": {"nom": company.name, "devise": company.currency},
                "tresorerie": {
                    "solde_bancaire_disponible": solde_bancaire_total,
                    "solde_comptable_512": treasury_services.solde_comptable_banque(company),
                    "definition": "Solde bancaire ≠ solde comptable ; rapprochement dédié.",
                },
                "facturation": {
                    "encours_clients_ttc": sum(f.reste_a_payer for f in encours_clients),
                    "factures_echues": factures_echues.count(),
                    "montant_echu_ttc": sum(f.reste_a_payer for f in factures_echues),
                    "reste_a_payer_fournisseurs": sum(f.reste_a_payer for f in a_payer_fournisseurs),
                },
                "abonnements": mrr_indicateurs(company),
                "rh": {
                    "salaries_actifs": Employee.objects.filter(company=company, status="actif").count(),
                    "absences_en_attente": absences_attente,
                    "frais_en_attente": frais_attente,
                },
                "conformite": conformite.get("compteurs", {}),
                "chiffre_affaires_mois": _ca_mois(company),
            }
        )


def _ca_mois(company) -> Decimal:
    """CA HT facturé ce mois (factures émises, sources identifiables)."""
    from django.db.models import Sum

    from apps.invoicing.models import Invoice, InvoiceStatus

    today = timezone.localdate()
    return (
        Invoice.objects.filter(
            company=company,
            issue_date__year=today.year,
            issue_date__month=today.month,
            status__in=(InvoiceStatus.EMISE, InvoiceStatus.PARTIELLEMENT_PAYEE,
                        InvoiceStatus.PAYEE, InvoiceStatus.EN_RETARD),
        ).aggregate(total=Sum("total_ht"))["total"]
        or Decimal(0)
    )


class AuditLogPermission(HasRole):
    pass


class AuditLogView(APIView):
    """Journal d'audit — administrateurs et direction."""

    permission_classes = (IsAuthenticated, HasRole.of(Roles.ADMIN, Roles.DIRECTION))

    def get(self, request):
        from rest_framework import serializers as drf_serializers

        qs = AuditLog.objects.filter(company=request.company).select_related("user")[:500]
        sensibilite = request.query_params.get("sensitivity")
        if sensibilite:
            qs = qs.filter(sensitivity=sensibilite)

        class S(drf_serializers.ModelSerializer):
            user_email = drf_serializers.EmailField(source="user.email", read_only=True)

            class Meta:
                model = AuditLog
                fields = ("id", "occurred_at", "user_email", "action", "method", "path",
                          "status_code", "ip_address", "sensitivity", "detail")

        return Response(S(qs, many=True).data)


class DocumentDownloadView(APIView):
    """Téléchargement sécurisé des documents RH (permissions vérifiées)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, pk):
        from apps.hr.models import EmployeeDocument

        document = EmployeeDocument.objects.filter(pk=pk, company=request.company).first()
        if document is None or not document.file:
            return Response({"detail": "Document introuvable."}, status=404)
        role = user_role(request)
        if role not in {Roles.ADMIN, Roles.RH, Roles.DIRECTION, Roles.PAIE}:
            # Salarié : uniquement ses documents marqués visibles
            profile = getattr(request.user, "employee_profile", None)
            if (
                not document.visible_to_employee
                or profile is None
                or document.employee_id != profile.id
            ):
                return Response({"detail": "Accès refusé.", "code": "acces_refuse"}, status=403)
        return FileResponse(document.file.open("rb"), as_attachment=True,
                            filename=document.label[:80])
