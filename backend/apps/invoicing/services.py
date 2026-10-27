"""Services de facturation : totaux, émission, avoirs, paiements, relances."""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import BusinessError
from apps.core.models import Sequence

from .models import (
    Client,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    InvoiceType,
    Payment,
    Quote,
    ReminderLog,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceLine,
)

CENT = Decimal("0.01")


def q2(v) -> Decimal:
    return Decimal(v).quantize(CENT)


def recalculer_invoice(invoice: Invoice, lines=None):
    """Recalcule les totaux HT/TVA/TTC côté serveur (jamais côté client)."""
    if lines is None:
        lines = list(invoice.lines.all())
    total_ht = Decimal(0)
    total_vat = Decimal(0)
    for line in lines:
        line.total_ht = q2(line.quantity * line.unit_price_ht)
        line.total_vat = q2(line.total_ht * line.vat_rate / 100)
        total_ht += line.total_ht
        total_vat += line.total_vat
    invoice.total_ht = total_ht
    invoice.total_vat = total_vat
    invoice.total_ttc = total_ht + total_vat
    return invoice


def recalculer_supplier_invoice(invoice: SupplierInvoice):
    total_ht = Decimal(0)
    total_vat = Decimal(0)
    for line in invoice.lines.all():
        line.total_ht = q2(line.quantity * line.unit_price_ht)
        line.total_vat = q2(line.total_ht * line.vat_rate / 100)
        total_ht += line.total_ht
        total_vat += line.total_vat
    invoice.total_ht = total_ht
    invoice.total_vat = total_vat
    invoice.total_ttc = total_ht + total_vat
    return invoice


@transaction.atomic
def remplacer_lignes_invoice(invoice: Invoice, lignes_data: list[dict]):
    """Remplace les lignes d'une facture BROUILLON et recalcule les totaux."""
    if invoice.status != InvoiceStatus.BROUILLON:
        raise BusinessError(
            "Seule une facture brouillon est modifiable ligne par ligne.",
            code="transition_interdite",
        )
    if not lignes_data:
        raise BusinessError("Une facture doit contenir au moins une ligne.", code="sans_lignes")
    invoice.lines.all().delete()
    lines = []
    for idx, data in enumerate(lignes_data):
        lines.append(
            InvoiceLine(
                invoice=invoice,
                order=idx,
                description=data.get("description", "Prestation"),
                quantity=Decimal(str(data.get("quantity", 1))),
                unit_price_ht=Decimal(str(data.get("unit_price_ht", 0))),
                vat_rate=Decimal(str(data.get("vat_rate", 20))),
            )
        )
    for line in lines:
        line.total_ht = q2(line.quantity * line.unit_price_ht)
        line.total_vat = q2(line.total_ht * line.vat_rate / 100)
    InvoiceLine.objects.bulk_create(lines)
    recalculer_invoice(invoice, lines)
    invoice.save(update_fields=["total_ht", "total_vat", "total_ttc", "updated_at"])
    return invoice


@transaction.atomic
def remplacer_lignes_supplier(invoice: SupplierInvoice, lignes_data: list[dict]):
    if invoice.status not in {SupplierInvoiceStatus.RECUE, "a_valider"}:
        raise BusinessError("Facture déjà validée : lignes non modifiables.", code="transition_interdite")
    invoice.lines.all().delete()
    lines = []
    for idx, data in enumerate(lignes_data or [{"description": "Facture fournisseur", "quantity": 1,
                                                "unit_price_ht": str(invoice.total_ht or 0),
                                                "vat_rate": "20"}]):
        lines.append(
            SupplierInvoiceLine(
                invoice=invoice,
                order=idx,
                description=data.get("description", "Charge"),
                quantity=Decimal(str(data.get("quantity", 1))),
                unit_price_ht=Decimal(str(data.get("unit_price_ht", 0))),
                vat_rate=Decimal(str(data.get("vat_rate", 20))),
            )
        )
    for line in lines:
        line.total_ht = q2(line.quantity * line.unit_price_ht)
        line.total_vat = q2(line.total_ht * line.vat_rate / 100)
    SupplierInvoiceLine.objects.bulk_create(lines)
    recalculer_supplier_invoice(invoice)
    invoice.save(update_fields=["total_ht", "total_vat", "total_ttc", "updated_at"])
    return invoice


@transaction.atomic
def emettre_invoice(invoice: Invoice) -> Invoice:
    """Émet la facture : numérotation séquentielle contrôlée, verrouillage."""
    if invoice.status != InvoiceStatus.BROUILLON:
        raise BusinessError("Facture déjà émise.", code="transition_interdite")
    if not invoice.lines.exists():
        raise BusinessError("Impossible d'émettre une facture sans lignes.", code="sans_lignes")
    year = invoice.issue_date.year
    prefix = {"facture": "FA", "avoir": "AV", "acompte": "AC"}[invoice.invoice_type]
    invoice.number = Sequence.allocate(invoice.company, key=f"invoice:{invoice.invoice_type}",
                                       prefix=prefix, year=year, padding=5)
    invoice.status = InvoiceStatus.EMISE
    invoice.save(update_fields=["number", "status", "updated_at"])
    return invoice


@transaction.atomic
def creer_avoir(invoice: Invoice, motif: str = "") -> Invoice:
    """Crée un avoir annulant intégralement la facture (correction conforme)."""
    if invoice.invoice_type != InvoiceType.FACTURE:
        raise BusinessError("Un avoir ne peut viser qu'une facture.", code="type_invalide")
    if invoice.status in {InvoiceStatus.BROUILLON, InvoiceStatus.ANNULEE}:
        raise BusinessError("Cette facture ne peut pas recevoir d'avoir.", code="transition_interdite")
    if invoice.avoirs.exists():
        raise BusinessError("Un avoir existe déjà pour cette facture.", code="avoir_existant")
    avoir = Invoice.objects.create(
        company=invoice.company,
        client=invoice.client,
        invoice_type=InvoiceType.AVOIR,
        status=InvoiceStatus.BROUILLON,
        issue_date=timezone.localdate(),
        due_date=timezone.localdate(),
        credit_note_of=invoice,
        notes=motif or f"Avoir d'annulation de {invoice.number}",
    )
    for line in invoice.lines.all():
        InvoiceLine.objects.create(
            invoice=avoir,
            order=line.order,
            description=f"ANNULATION — {line.description}",
            quantity=line.quantity,
            unit_price_ht=-line.unit_price_ht,
            vat_rate=line.vat_rate,
            total_ht=-line.total_ht,
            total_vat=-line.total_vat,
        )
    recalculer_invoice(avoir)
    avoir.save(update_fields=["total_ht", "total_vat", "total_ttc"])
    invoice.status = InvoiceStatus.ANNULEE
    invoice.save(update_fields=["status", "updated_at"])
    return avoir


@transaction.atomic
def enregistrer_paiement(company, invoice=None, supplier_invoice=None, **kwargs) -> Payment:
    """Enregistre un règlement et met à jour le statut de la facture.

    Idempotent côté données : chaque paiement est un enregistrement distinct,
    jamais un recalcul destructeur.
    """
    if not invoice and not supplier_invoice:
        raise BusinessError("Paiement sans facture associée.", code="paiement_orphelin")
    direction = "recu" if invoice else "emis"
    payment = Payment.objects.create(
        company=company, invoice=invoice, supplier_invoice=supplier_invoice,
        direction=direction, **kwargs,
    )
    cible = invoice or supplier_invoice
    total_paye = sum(p.amount for p in cible.paiements.all())
    cible.amount_paid = q2(total_paye)
    if cible.amount_paid >= cible.total_ttc:
        nouveau_statut = "payee" if invoice else "validee"
    elif cible.amount_paid > 0:
        nouveau_statut = "partielle"
    else:
        nouveau_statut = cible.status

    # Mapping explicite selon le type de facture
    if invoice:
        mapping = {
            "payee": InvoiceStatus.PAYEE,
            "partielle": InvoiceStatus.PARTIELLEMENT_PAYEE,
        }
        cible.status = mapping.get(nouveau_statut, cible.status)
    else:
        from .models import SupplierInvoiceStatus as Sis

        mapping = {"payee": Sis.PAYEE, "partielle": Sis.PARTIELLEMENT_PAYEE}
        cible.status = mapping.get(nouveau_statut, cible.status)
    cible.save(update_fields=["amount_paid", "status", "updated_at"])
    return payment


@transaction.atomic
def relancer_facture(invoice: Invoice, user, level: int, note: str = "") -> ReminderLog:
    """Trace une relance. Le niveau est unique par facture (pas de doublon)."""
    if invoice.status not in {InvoiceStatus.EMISE, InvoiceStatus.PARTIELLEMENT_PAYEE, InvoiceStatus.EN_RETARD}:
        raise BusinessError("Seules les factures émises/échues sont relançables.", code="transition_interdite")
    if ReminderLog.objects.filter(invoice=invoice, level=level).exists():
        raise BusinessError("Une relance de ce niveau existe déjà.", code="relance_doublon")
    return ReminderLog.objects.create(
        company=invoice.company, invoice=invoice, level=level, sent_by=user, note=note
    )


def marquer_factures_echues_company(company) -> int:
    """Marque EN_RETARD les factures échues non soldées."""
    today = timezone.localdate()
    factures = Invoice.objects.filter(
        company=company,
        status__in=(InvoiceStatus.EMISE, InvoiceStatus.PARTIELLEMENT_PAYEE),
        due_date__lt=today,
    )
    count = factures.update(status=InvoiceStatus.EN_RETARD)
    from .models import SupplierInvoiceStatus as Sis

    fournisseurs = SupplierInvoice.objects.filter(
        company=company,
        status__in=(Sis.RECUE, Sis.A_VALIDER, Sis.VALIDEE, Sis.PARTIELLEMENT_PAYEE),
        due_date__lt=today,
    )
    for f in fournisseurs:
        f.status = Sis.EN_RETARD
        f.save(update_fields=["status"])
    return count


@transaction.atomic
def convertir_devis(quote: Quote) -> Invoice:
    """Convertit un devis accepté en facture brouillon (lignes recopiées)."""
    if quote.status != QuoteStatus.ACCEPTE:
        raise BusinessError("Seul un devis accepté peut être facturé.", code="transition_interdite")
    invoice = Invoice.objects.create(
        company=quote.company,
        client=quote.client,
        status=InvoiceStatus.BROUILLON,
        issue_date=timezone.localdate(),
        due_date=timezone.localdate() + timedelta(days=quote.client.payment_terms_days),
        source=f"devis:{quote.number}",
    )
    for line in quote.lines.all():
        InvoiceLine.objects.create(
            invoice=invoice, order=line.order, description=line.description,
            quantity=line.quantity, unit_price_ht=line.unit_price_ht, vat_rate=line.vat_rate,
        )
    recalculer_invoice(invoice)
    invoice.save(update_fields=["total_ht", "total_vat", "total_ttc"])
    return invoice


def calculer_totaux_devis(quote: Quote):
    total_ht = Decimal(0)
    total_vat = Decimal(0)
    for line in quote.lines.all():
        ht = q2(line.quantity * line.unit_price_ht)
        total_ht += ht
        total_vat += q2(ht * line.vat_rate / 100)
    quote.total_ht = total_ht
    quote.total_vat = total_vat
    quote.total_ttc = total_ht + total_vat
    quote.save(update_fields=["total_ht", "total_vat", "total_ttc"])
    return quote
