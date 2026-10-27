"""Pont facturation → comptabilité (sections 6 et 8 du cahier des charges)."""

from decimal import Decimal

from django.db import transaction

from apps.accounting.services import creer_ecriture
from apps.core.exceptions import BusinessError

from .models import Invoice, InvoiceStatus, SupplierInvoice, SupplierInvoiceStatus

COMPTE_CLIENT = "411000"
COMPTE_FOURNISSEUR = "401000"
COMPTE_TVA_COLLECTEE = "445710"
COMPTE_TVA_DEDUCTIBLE = "445660"
COMPTE_PRODUIT_DEFAUT = "706000"
COMPTE_CHARGE_DEFAUT = "603100"


@transaction.atomic
def comptabiliser_facture_client(invoice: Invoice, user) -> object:
    """Écriture des ventes : 411 débit / 706 crédit / 4457 TVA collectée."""
    if invoice.status == InvoiceStatus.BROUILLON:
        raise BusinessError("Émettez la facture avant comptabilisation.", code="non_emise")
    if invoice.accounting_entry_id:
        raise BusinessError("Facture déjà comptabilisée.", code="deja_comptabilisee")

    signe = Decimal(1)
    # Un avoir annule : montants négatifs stockés, les lignes le portent déjà
    lignes = [
        {
            "account": COMPTE_CLIENT,
            "label": f"{invoice.get_invoice_type_display()} {invoice.number} — {invoice.client.name}",
            "debit": abs(invoice.total_ttc),
            "credit": Decimal(0),
            "auxiliary": invoice.client.name,
        }
    ]
    if invoice.total_ht:
        lignes.append(
            {
                "account": COMPTE_PRODUIT_DEFAUT,
                "label": f"Produit — {invoice.number}",
                "debit": Decimal(0),
                "credit": abs(invoice.total_ht),
            }
        )
    if invoice.total_vat:
        lignes.append(
            {
                "account": COMPTE_TVA_COLLECTEE,
                "label": f"TVA collectée — {invoice.number}",
                "debit": Decimal(0),
                "credit": abs(invoice.total_vat),
            }
        )
    entry = creer_ecriture(
        invoice.company, "VE", invoice.issue_date,
        f"{invoice.get_invoice_type_display()} {invoice.number} — {invoice.client.name}",
        lignes, user=user, valider=True,
        source=("invoicing.Invoice", str(invoice.id), invoice.number),
    )
    invoice.accounting_entry = entry
    invoice.save(update_fields=["accounting_entry", "updated_at"])
    return entry


@transaction.atomic
def comptabiliser_facture_fournisseur(invoice: SupplierInvoice, user) -> object:
    """Écriture des achats : 6xx débit / 44566 TVA déductible / 401 crédit."""
    if invoice.status not in {SupplierInvoiceStatus.VALIDEE, SupplierInvoiceStatus.PARTIELLEMENT_PAYEE, SupplierInvoiceStatus.PAYEE}:
        raise BusinessError(
            "La facture doit d'abord être validée par un humain.", code="non_validee"
        )
    if invoice.accounting_entry_id:
        raise BusinessError("Facture déjà comptabilisée.", code="deja_comptabilisee")

    account_charge = invoice.expense_account or invoice.supplier.default_expense_account or COMPTE_CHARGE_DEFAUT
    lignes = [
        {
            "account": account_charge,
            "label": f"{invoice.internal_number or invoice.supplier_reference} — {invoice.supplier.name}",
            "debit": abs(invoice.total_ht),
            "credit": Decimal(0),
        }
    ]
    if invoice.total_vat:
        lignes.append(
            {
                "account": COMPTE_TVA_DEDUCTIBLE,
                "label": f"TVA déductible — {invoice.internal_number or invoice.supplier_reference}",
                "debit": abs(invoice.total_vat),
                "credit": Decimal(0),
            }
        )
    lignes.append(
        {
            "account": COMPTE_FOURNISSEUR,
            "label": f"{invoice.internal_number or invoice.supplier_reference}",
            "debit": Decimal(0),
            "credit": abs(invoice.total_ttc),
            "auxiliary": invoice.supplier.name,
        }
    )
    entry = creer_ecriture(
        invoice.company, "AC", invoice.invoice_date,
        f"Facture fournisseur {invoice.internal_number or invoice.supplier_reference}",
        lignes, user=user, valider=True,
        source=("invoicing.SupplierInvoice", str(invoice.id),
                invoice.internal_number or invoice.supplier_reference),
    )
    invoice.accounting_entry = entry
    invoice.save(update_fields=["accounting_entry", "updated_at"])
    return entry


@transaction.atomic
def comptabiliser_paiement(payment, user) -> object:
    """Écriture de banque pour un règlement constaté.

    Client reçu : 512 débit / 411 crédit. Fournisseur émis : 401 débit / 512 crédit.
    """
    from apps.accounting.models import FiscalYear  # noqa: F401 (cohérence d'exercice gérée dans creer_ecriture)

    if payment.invoice:
        invoice = payment.invoice
        lignes = [
            {"account": "512000", "label": f"Règlement {invoice.number}", "debit": payment.amount, "credit": 0},
            {"account": COMPTE_CLIENT, "label": f"Règlement {invoice.number}",
             "debit": 0, "credit": payment.amount, "auxiliary": invoice.client.name},
        ]
        label = f"Encaissement {invoice.number} — {invoice.client.name}"
        source = ("invoicing.Payment", str(payment.id), invoice.number)
    else:
        invoice = payment.supplier_invoice
        lignes = [
            {"account": COMPTE_FOURNISSEUR, "label": f"Règlement {invoice.internal_number}",
             "debit": payment.amount, "credit": 0, "auxiliary": invoice.supplier.name},
            {"account": "512000", "label": f"Règlement {invoice.internal_number}",
             "debit": 0, "credit": payment.amount},
        ]
        label = f"Décaissement {invoice.internal_number} — {invoice.supplier.name}"
        source = ("invoicing.Payment", str(payment.id), invoice.internal_number)
    return creer_ecriture(payment.company, "BQ", payment.date, label, lignes,
                          user=user, valider=True, source=source)
