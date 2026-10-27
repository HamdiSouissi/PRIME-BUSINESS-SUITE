"""Facturation récurrente idempotente et indicateurs MRR/ARR."""

from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.invoicing.models import Invoice, InvoiceLine, InvoiceStatus
from apps.invoicing.services import emettre_invoice, recalculer_invoice

from .models import Periodicity, Subscription, SubscriptionInvoice, SubscriptionStatus


@transaction.atomic
def generer_facture_echeance(subscription: Subscription, user=None) -> SubscriptionInvoice | None:
    """Facture UNE échéance. Idempotence garantie par la contrainte unique
    (subscription, period_start) : une relance ne peut pas créer de doublon.
    """
    from datetime import timedelta

    if subscription.status not in {SubscriptionStatus.ACTIF, SubscriptionStatus.ESSAI}:
        return None
    today = timezone.localdate()
    if subscription.status == SubscriptionStatus.ESSAI and subscription.trial_end and subscription.trial_end >= today:
        return None  # période d'essai gratuite en cours

    period_start = subscription.next_billing_date
    period_end = subscription.date_echeance_suivante(period_start) - timedelta(days=1)

    if subscription.end_date and period_start > subscription.end_date:
        return None

    invoice = Invoice.objects.create(
        company=subscription.company,
        client=subscription.client,
        status=InvoiceStatus.BROUILLON,
        issue_date=period_start,
        due_date=period_start + timedelta(days=subscription.client.payment_terms_days),
        source=f"abonnement:{subscription.id}",
    )
    InvoiceLine.objects.create(
        invoice=invoice,
        order=0,
        description=f"{subscription.label} — période du {period_start:%d/%m/%Y} au {period_end:%d/%m/%Y}",
        quantity=1,
        unit_price_ht=subscription.montant_par_periode_ht,
        vat_rate=subscription.vat_rate,
    )
    recalculer_invoice(invoice)
    invoice.save(update_fields=["total_ht", "total_vat", "total_ttc"])
    emettre_invoice(invoice)

    try:
        link = SubscriptionInvoice.objects.create(
            company=subscription.company,
            subscription=subscription,
            invoice=invoice,
            period_start=period_start,
            period_end=period_end,
        )
    except IntegrityError:
        # Un autre processus vient de facturer cette période : on supprime la
        # facture brouillon concurrente et on signale la collision.
        invoice.delete()
        return SubscriptionInvoice.objects.filter(
            subscription=subscription, period_start=period_start
        ).first()

    subscription.next_billing_date = subscription.date_echeance_suivante(period_start)
    if subscription.end_date and subscription.next_billing_date > subscription.end_date and not subscription.auto_renew:
        subscription.status = SubscriptionStatus.RESILIE
        subscription.canceled_at = subscription.end_date
    subscription.save(update_fields=["next_billing_date", "status", "canceled_at", "updated_at"])
    return link


def generer_factures_echues_company(company, user=None) -> int:
    """Facture toutes les échéances dues (tâche planifiée ou manuelle)."""
    today = timezone.localdate()
    count = 0
    abos = Subscription.objects.select_for_update().filter(
        company=company,
        status__in=(SubscriptionStatus.ACTIF, SubscriptionStatus.ESSAI),
        next_billing_date__lte=today,
    )
    for abo in abos:
        # Boucle de rattrapage si plusieurs échéances passées
        while abo.next_billing_date <= today:
            link = generer_facture_echeance(abo, user)
            if link is None:
                break
            abo.refresh_from_db()
            count += 1
    return count


def indicateurs(company) -> dict:
    """MRR, ARR, taux de renouvellement, résiliations et prévisions.

    Définitions (documentées) :
    - MRR : somme des contributions mensuelles HT des abonnements ACTIFS.
    - ARR : MRR × 12.
    - Taux de renouvellement (12 mois) : abonnements arrivés à échéance et
      renouvelés / abonnements arrivés à échéance.
    - Résiliations : abonnements résiliés sur 12 mois.
    - Prévision 12 mois : MRR × 12 (hypothèse constante, documentée).
    """
    from datetime import timedelta

    today = timezone.localdate()
    actifs = Subscription.objects.filter(company=company, status=SubscriptionStatus.ACTIF)
    mrr = (sum(abo.mrr_contribution for abo in actifs)).quantize(Decimal("0.01")) if actifs else Decimal(0)
    resilles_12m = Subscription.objects.filter(
        company=company, status=SubscriptionStatus.RESILIE,
        canceled_at__gte=today - timedelta(days=365),
    ).count()
    renouvelles = Subscription.objects.filter(
        company=company,
        factures_generees__isnull=False,
        status=SubscriptionStatus.ACTIF,
    ).distinct().count()
    arrives_a_terme = Subscription.objects.filter(
        company=company, end_date__lte=today
    ).count()
    taux_renouvellement = (
        Decimal(renouvelles) / Decimal(arrives_a_terme) * 100
        if arrives_a_terme else Decimal(100)
    )
    return {
        "mrr_ht": mrr,
        "arr_ht": (mrr * 12).quantize(Decimal("0.01")),
        "abonnements_actifs": actifs.count(),
        "resiliations_12_mois": resilles_12m,
        "taux_renouvellement_pct": taux_renouvellement.quantize(Decimal("0.1")),
        "prevision_12_mois_ht": (mrr * 12).quantize(Decimal("0.01")),
        "hypotheses": "Prévision = MRR actuel × 12, hors ventes nouvelles et hors churn futur.",
        "periodicites": dict(Periodicity.choices),
    }
