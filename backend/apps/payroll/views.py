"""API de la paie : jeux de règles, cycles, bulletins, préparation DSN."""

from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessError
from apps.core.permissions import HasRole, ReadOnlyOrRole, Roles, user_role
from apps.core.viewsets import CompanyScopedViewSet

from . import services
from .models import (
    ContributionRule,
    DSNExport,
    Payslip,
    PayslipStatus,
    PayrollParameterSet,
    PayrollRun,
    RulesetStatus,
    RunStatus,
)
from .serializers import (
    ContributionRuleSerializer,
    DSNExportSerializer,
    PayslipDetailSerializer,
    PayslipInputsSerializer,
    PayslipListSerializer,
    PayrollParameterSetSerializer,
    PayrollRunSerializer,
)

PAIE_ROLES = (Roles.ADMIN, Roles.PAIE)
PAIE_DIRECTION = (Roles.ADMIN, Roles.PAIE, Roles.DIRECTION, Roles.FINANCE)


class PayrollParameterSetViewSet(CompanyScopedViewSet):
    queryset = PayrollParameterSet.objects.prefetch_related("rules").all()
    serializer_class = PayrollParameterSetSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*PAIE_ROLES))
    filterset_fields = ("status",)

    @action(detail=False, methods=["post"], url_path="reference-2025",
            permission_classes=[IsAuthenticated, HasRole.of(*PAIE_ROLES)])
    def creer_reference(self, request):
        """Crée le jeu de référence France 2025 (statut provisoire)."""
        company = getattr(request, "company", None)
        params = services.creer_ruleset_reference(company, request.user)
        return Response(PayrollParameterSetSerializer(params).data, status=201)

    @action(detail=True, methods=["post"], url_path="verifier",
            permission_classes=[IsAuthenticated, HasRole.of(*PAIE_ROLES)])
    def verifier(self, request, pk=None):
        """Marque le jeu comme vérifié par un expert (trace obligatoire)."""
        params = self.get_object()
        note = request.data.get("note", "").strip()
        if not note:
            return Response(
                {
                    "detail": "Une note de vérification est obligatoire (référence "
                    "de la vérification effectuée par le spécialiste).",
                    "code": "note_requise",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        params.status = RulesetStatus.VERIFIE
        params.verified_by = request.user
        params.verified_at = timezone.now()
        params.verification_note = note
        params.save(update_fields=["status", "verified_by", "verified_at", "verification_note", "updated_at"])
        return Response(PayrollParameterSetSerializer(params).data)


class ContributionRuleViewSet(CompanyScopedViewSet):
    queryset = ContributionRule.objects.all()
    serializer_class = ContributionRuleSerializer
    permission_classes = (IsAuthenticated, HasRole.of(*PAIE_ROLES))

    def perform_update(self, serializer):
        rule = self.get_object()
        if rule.parameter_set.payslips.exists():
            raise BusinessError(
                "Ce jeu de règles a déjà servi à des bulletins : les règles sont "
                "gelées. Créez une nouvelle version du jeu de paramètres.",
                code="regles_gelees",
            )
        serializer.save()


class PayrollRunViewSet(CompanyScopedViewSet):
    queryset = PayrollRun.objects.prefetch_related("payslips").all()
    serializer_class = PayrollRunSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*PAIE_DIRECTION))
    filterset_fields = ("year", "month", "status")

    def perform_create(self, serializer):
        month = serializer.validated_data.get("month")
        if not 1 <= month <= 12:
            raise BusinessError("Mois invalide.", code="mois_invalide")
        serializer.save(
            company=getattr(self.request, "company", None),
            started_by=self.request.user,
        )

    @action(detail=True, methods=["get"], url_path="controle",
            permission_classes=[IsAuthenticated, HasRole.of(*PAIE_ROLES)])
    def controle(self, request, pk=None):
        """Étape 2 : contrôle des données manquantes."""
        run = self.get_object()
        manquantes = services.verifier_donnees_cycle(run)
        run.status = RunStatus.CONTROLE
        run.log_step(request.user, f"Contrôle des données : {len(manquantes)} anomalie(s).")
        run.save()
        return Response({"anomalies": manquantes})

    @action(detail=True, methods=["post"], url_path="simuler",
            permission_classes=[IsAuthenticated, HasRole.of(*PAIE_ROLES)])
    def simuler(self, request, pk=None):
        """Étape 3 : génération/simulation des bulletins."""
        run = self.get_object()
        bulletins = services.generer_simulation(run, request.user)
        return Response({"bulletins": len(bulletins), "status": run.status})

    @action(detail=True, methods=["get"], url_path="anomalies",
            permission_classes=[IsAuthenticated, HasRole.of(*PAIE_ROLES)])
    def anomalies(self, request, pk=None):
        """Étapes 4-5 : comparaison avec le cycle précédent."""
        run = self.get_object()
        return Response({"anomalies": services.anomalies_vs_precedent(run)})

    @action(detail=True, methods=["post"], url_path="valider",
            permission_classes=[IsAuthenticated, HasRole.of(*PAIE_ROLES)])
    def valider(self, request, pk=None):
        """Étape 6 : validation définitive (bloquée si règles provisoires)."""
        run = self.get_object()
        services.valider_cycle(run, request.user)
        return Response(PayrollRunSerializer(run).data)

    @action(detail=True, methods=["post"], url_path="cloturer",
            permission_classes=[IsAuthenticated, HasRole.of(*PAIE_ROLES)])
    def cloturer(self, request, pk=None):
        """Clôture et archivage du cycle."""
        run = self.get_object()
        services.cloturer_cycle(run, request.user)
        return Response(PayrollRunSerializer(run).data)

    @action(detail=True, methods=["post"], url_path="editer-bulletins",
            permission_classes=[IsAuthenticated, HasRole.of(*PAIE_ROLES)])
    def editer_bulletins(self, request, pk=None):
        """Étapes 7-8 : génération des PDF et mise à disposition."""
        run = self.get_object()
        count = 0
        for bulletin in run.payslips.all():
            services.editer_bulletin(bulletin, request.user)
            count += 1
        run.log_step(request.user, f"Bulletins édités et mis à disposition ({count}).")
        run.save()
        return Response({"edites": count})

    @action(detail=True, methods=["post"], url_path="dsn",
            permission_classes=[IsAuthenticated, HasRole.of(*PAIE_ROLES)])
    def preparer_dsn(self, request, pk=None):
        """Prépare un export des données DSN (NON transmis — intégration requise)."""
        from . import services_dsn

        run = self.get_object()
        export = services_dsn.preparer_dsn(run, request.user)
        return Response(DSNExportSerializer(export).data, status=201)


class PayslipViewSet(CompanyScopedViewSet):
    queryset = Payslip.objects.select_related("employee", "run", "parameter_set").all()
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("run", "employee", "status", "provisional")

    def get_serializer_class(self):
        if self.action == "list":
            return PayslipListSerializer
        return PayslipDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        role = user_role(self.request)
        if role == Roles.SALARIE:
            profile = getattr(self.request.user, "employee_profile", None)
            if profile is None:
                return qs.none()
            # Un salarié ne voit que ses bulletins MISES À DISPOSITION.
            return qs.filter(employee=profile, published_to_employee=True)
        return qs

    @action(detail=True, methods=["patch"], url_path="variables",
            permission_classes=[IsAuthenticated, HasRole.of(*PAIE_ROLES)])
    def variables(self, request, pk=None):
        """Saisie des variables mensuelles (primes, absences, HS…).

        Rejoue ensuite le calcul de façon déterministe sur le bulletin.
        Interdit sur un bulletin validé/clôturé (traçabilité)."""
        payslip = self.get_object()
        if payslip.status in {PayslipStatus.VALIDE, PayslipStatus.EDITE, PayslipStatus.CLOTURE}:
            raise BusinessError(
                "Bulletin définitif : variables non modifiables. Créez un bulletin "
                "correctif sur un cycle suivant.",
                code="bulletin_gele",
            )
        ser = PayslipInputsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        inputs = dict(payslip.inputs or {})
        for key, value in ser.validated_data.items():
            if key == "taux_pas":
                inputs[key] = str(value)
            else:
                inputs[key] = value
        payslip.inputs = inputs
        payslip.save(update_fields=["inputs", "updated_at"])
        rules = list(payslip.parameter_set.rules.all())
        from .engine import compute_payslip, hash_result

        result = compute_payslip(payslip.inputs, payslip.parameter_set, rules)
        payslip.result = result
        payslip.result_hash = hash_result(result)
        totaux = result["totaux"]
        payslip.brut = totaux["brut"]
        payslip.total_cotisations_salariales = totaux["total_cotisations_salariales"]
        payslip.total_cotisations_patronales = totaux["total_cotisations_patronales"]
        payslip.allegements = totaux["allegements"]
        payslip.net_social = totaux["net_social"]
        payslip.net_imposable = totaux["net_imposable"]
        payslip.prelevement_a_la_source = totaux["prelevement_a_la_source"]
        payslip.net_a_payer = totaux["net_a_payer"]
        payslip.cout_employeur = totaux["cout_employeur"]
        payslip.save()
        payslip.lines.all().delete()
        from .models import PayslipLine

        PayslipLine.objects.bulk_create(
            [
                PayslipLine(
                    payslip=payslip,
                    section=l["section"],
                    code=l["code"],
                    label=l["label"],
                    base=l["base"],
                    rate_salarial=l["rate_salarial"],
                    amount_salarial=l["amount_salarial"],
                    rate_patronal=l["rate_patronal"],
                    amount_patronal=l["amount_patronal"],
                    is_allegement=l["is_allegement"],
                    order=idx,
                )
                for idx, l in enumerate(result["cotisations"])
            ]
        )
        return Response(PayslipDetailSerializer(payslip).data)

    @action(detail=True, methods=["post"], url_path="editer",
            permission_classes=[IsAuthenticated, HasRole.of(*PAIE_ROLES)])
    def editer(self, request, pk=None):
        payslip = self.get_object()
        services.editer_bulletin(payslip, request.user)
        return Response(PayslipDetailSerializer(payslip).data)

    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        """Téléchargement sécurisé du bulletin (propriétaire ou gestionnaire)."""
        payslip = self.get_object()
        if not payslip.pdf:
            return Response({"detail": "PDF non généré.", "code": "pas_de_pdf"}, status=404)
        return FileResponse(
            payslip.pdf.open("rb"),
            content_type="application/pdf",
            as_attachment=True,
            filename=f"bulletin-{payslip.number or payslip.id}.pdf",
        )


class DSNExportViewSet(CompanyScopedViewSet):
    queryset = DSNExport.objects.select_related("run", "generated_by").all()
    serializer_class = DSNExportSerializer
    permission_classes = (IsAuthenticated, ReadOnlyOrRole.of(*PAIE_ROLES))
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=True, methods=["get"], url_path="telecharger",
            permission_classes=[IsAuthenticated, HasRole.of(*PAIE_ROLES)])
    def telecharger(self, request, pk=None):
        export = self.get_object()
        if not export.file:
            return Response({"detail": "Aucun fichier généré."}, status=404)
        return FileResponse(export.file.open("rb"), as_attachment=True,
                            filename=f"dsn-preparation-{export.id}.json")
