"""Services de trésorerie : import CSV, rapprochement, prévisionnel.

Deux notions sont strictement séparées (cahier des charges, section 7) :
- le SOLDE BANCAIRE : solde initial + opérations importées ;
- le SOLDE COMPTABLE : solde du compte 512 dans la comptabilité.
Le rapprochement met en correspondance les deux mondes.
"""

import csv
import io
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.exceptions import BusinessError

from .models import BankAccount, BankTransaction, CashEvent

CENT = Decimal("0.01")


def solde_bancaire(account: BankAccount, au: date | None = None) -> Decimal:
    qs = account.operations.all()
    if au:
        qs = qs.filter(date__lte=au)
    total = qs.aggregate(total=Sum("amount"))["total"] or Decimal(0)
    return (account.initial_balance or Decimal(0)) + total


def solde_comptable_banque(company, au: date | None = None) -> Decimal:
    """Solde du/des comptes 512 en comptabilité (soldes validés)."""
    from apps.accounting.models import EntryLine, EntryStatus

    qs = EntryLine.objects.filter(
        entry__company=company,
        account__number__startswith="512",
        entry__status__in=(EntryStatus.VALIDEE, EntryStatus.CONTRE_PASSEE),
    )
    if au:
        qs = qs.filter(entry__date__lte=au)
    totals = qs.aggregate(d=Sum("debit"), c=Sum("credit"))
    return (totals["d"] or Decimal(0)) - (totals["c"] or Decimal(0))


# ---------------------------------------------------------------------------
# Import de relevés
# ---------------------------------------------------------------------------

FORMATS_ACCEPTES = (
    "Colonnes attendues (fr) : date;libelle;montant[;methode;reference]. "
    "Dates JJ/MM/AAAA ou AAAA-MM-JJ ; montant au format français ou point ; "
    "séparateur « ; »."
)


def _parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            from datetime import datetime

            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise BusinessError(f"Date illisible : {value}", code="import_date")


def _parse_amount(value: str) -> Decimal:
    cleaned = value.strip().replace(" ", "").replace(",", ".")
    try:
        return Decimal(cleaned).quantize(CENT)
    except Exception:
        raise BusinessError(f"Montant illisible : {value}", code="import_montant")


@transaction.atomic
def importer_csv(account: BankAccount, contenu: bytes, user=None) -> dict:
    """Importe un relevé CSV. Les doublons sont ignorés (empreinte dédiée)."""
    text = contenu.decode("utf-8-sig", errors="replace")
    # Détection séparateur ; ou ,
    echantillon = text[:512]
    dialect = csv.Sniffer().sniff(echantillon, delimiters=";,")
    reader = csv.reader(io.StringIO(text), dialect)
    lignes = list(reader)
    if not lignes:
        raise BusinessError("Fichier vide.", code="fichier_vide")

    entete = [c.strip().lower() for c in lignes[0]]
    a_entete = any(mot in " ".join(entete) for mot in ("date", "libelle", "mémo", "montant", "amount"))
    colonnes = {"date": 0, "libelle": 1, "montant": 2}
    if a_entete:
        for i, nom in enumerate(entete):
            if "date" in nom:
                colonnes["date"] = i
            elif "libell" in nom or "label" in nom or "mémo" in nom or "memo" in nom:
                colonnes["libelle"] = i
            elif "montant" in nom or "amount" in nom or "débit" in nom or "credit" in nom:
                colonnes["montant"] = i
        lignes = lignes[1:]

    crees, ignores = 0, 0
    erreurs = []
    for idx, ligne in enumerate(lignes, start=2):
        if not ligne or all(not c.strip() for c in ligne):
            continue
        try:
            date_op = _parse_date(ligne[colonnes["date"]])
            libelle = ligne[colonnes["libelle"]].strip()[:500]
            montant = _parse_amount(ligne[colonnes["montant"]])
        except BusinessError as exc:
            erreurs.append(f"Ligne {idx} : {exc.message}")
            continue
        empreinte = BankTransaction.compute_hash(account.id, date_op, libelle, montant)
        _, created = BankTransaction.objects.get_or_create(
            bank_account=account,
            dedupe_hash=empreinte,
            defaults={
                "company": account.company,
                "date": date_op,
                "label": libelle,
                "amount": montant,
                "method": (ligne[colonnes.get("methode", 3)].strip() if len(ligne) > 3 else "")[:32],
                "reference": (ligne[colonnes.get("reference", 4)].strip() if len(ligne) > 4 else "")[:128],
            },
        )
        if created:
            crees += 1
        else:
            ignores += 1
    return {"importees": crees, "doublons_ignores": ignores, "erreurs": erreurs}


# ---------------------------------------------------------------------------
# Rapprochement
# ---------------------------------------------------------------------------

@transaction.atomic
def rapprocher(transaction_obj: BankTransaction, payment, user) -> BankTransaction:
    if transaction_obj.reconciled:
        raise BusinessError("Opération déjà rapprochée.", code="deja_rapprochee")
    # Cohérence de sens et de montant
    if abs(transaction_obj.amount) != abs(payment.amount):
        raise BusinessError(
            "Les montants diffèrent : rapprochement refusé.", code="montant_different"
        )
    sens_ok = (transaction_obj.amount > 0) == (payment.direction == "recu")
    if not sens_ok:
        raise BusinessError("Sens incohérent entre opération et règlement.", code="sens_incoherent")
    transaction_obj.payment = payment
    transaction_obj.reconciled = True
    transaction_obj.reconciled_by = user
    transaction_obj.reconciled_at = timezone.now()
    transaction_obj.save()
    return transaction_obj


def suggestions_rapprochement(transaction_obj: BankTransaction) -> list:
    """Paiements candidats même sens/montant, non encore liés au compte."""
    from apps.invoicing.models import Payment

    qs = Payment.objects.filter(company=transaction_obj.company, amount=abs(transaction_obj.amount))
    qs = qs.filter(direction="recu" if transaction_obj.amount > 0 else "emis")
    qs = qs.filter(date__gte=transaction_obj.date - timedelta(days=45),
                   date__lte=transaction_obj.date + timedelta(days=45))
    return list(qs.select_related("invoice", "supplier_invoice")[:10])


# ---------------------------------------------------------------------------
# Prévisionnel de trésorerie
# ---------------------------------------------------------------------------

SCENARIOS = {
    # Multiplicateur de probabilité d'encaissement des factures clients et
    # délai additionnel (jours) appliqué aux encaissements attendus.
    "optimiste": {"probabilite": Decimal("1.05"), "decalage_jours": 0},
    "central": {"probabilite": Decimal("0.90"), "decalage_jours": 7},
    "prudent": {"probabilite": Decimal("0.75"), "decalage_jours": 21},
}
HORIZONS = (30, 60, 90, 180)


def _periodes_supplementaires(start: date, months: int) -> list[date]:
    """Retourne les dates mensuelles successives (même jour si possible)."""
    dates = []
    year, month = start.year, start.month
    for _ in range(months):
        month += 1
        if month > 12:
            month = 1
            year += 1
        day = min(start.day, 28)  # sécurité fin de mois
        dates.append(date(year, month, day))
    return dates


def previsionnel(company, scenario: str = "central", point_depart: date | None = None) -> dict:
    """Prévision de trésorerie sur 30/60/90/180 jours.

    Sources : factures clients impayées (à l'échéance), abonnements à
    échéance, factures fournisseurs validées, paie (dernier cycle), événements
    CashEvent manuels. Définitions documentées dans docs/.
    """
    from apps.invoicing.models import Invoice, InvoiceStatus, SupplierInvoice, SupplierInvoiceStatus
    from apps.payroll.models import PayrollRun, RunStatus
    from apps.subscriptions.models import Subscription

    scenario_conf = SCENARIOS.get(scenario, SCENARIOS["central"])
    proba = min(scenario_conf["probabilite"], Decimal(1))
    decalage = scenario_conf["decalage_jours"]
    today = point_depart or timezone.localdate()

    # Solde bancaire disponible = somme des comptes actifs
    comptes = list(BankAccount.objects.filter(company=company, is_active=True))
    solde_initial = sum(solde_bancaire(compte, today) for compte in comptes)

    evenements = []  # (date, montant signé, libellé)

    # Encaissements : factures clients émises non soldées
    factures = Invoice.objects.filter(
        company=company,
        status__in=(InvoiceStatus.EMISE, InvoiceStatus.EN_RETARD, InvoiceStatus.PARTIELLEMENT_PAYEE),
    )
    for facture in factures:
        reste = facture.reste_a_payer
        if reste <= 0:
            continue
        date_effet = max(facture.due_date, today) + timedelta(days=decalage)
        montant = reste * proba
        evenements.append((date_effet, montant, f"Règlement attendu {facture.number}"))

    # Décaissements : factures fournisseurs validées non soldées
    fournisseurs = SupplierInvoice.objects.filter(
        company=company,
        status__in=(SupplierInvoiceStatus.VALIDEE, SupplierInvoiceStatus.PARTIELLEMENT_PAYEE,
                    SupplierInvoiceStatus.EN_RETARD),
    )
    for facture in fournisseurs:
        reste = facture.reste_a_payer
        if reste > 0:
            evenements.append((max(facture.due_date, today), -reste,
                               f"Fournisseur {facture.supplier.name}"))

    # Abonnements clients : prochaines échéances (périodicité)
    for abo in Subscription.objects.filter(company=company, status="actif"):
        for idx, date_ech in enumerate(_periodes_supplementaires(today, 6)):
            if date_ech > today + timedelta(days=HORIZONS[-1]):
                break
            montant = abo.montant_par_periode_ttc * proba
            evenements.append((date_ech, montant, f"Abonnement {abo.label}"))

    # Masse salariale : coût employeur du dernier cycle, mensuellement
    dernier_cycle = (
        PayrollRun.objects.filter(company=company, status__in=(RunStatus.VALIDE, RunStatus.CLOTURE))
        .order_by("-year", "-month")
        .first()
    )
    if dernier_cycle is not None:
        cout = dernier_cycle.payslips.aggregate(total=Sum("cout_employeur"))["total"] or Decimal(0)
        if cout > 0:
            for date_ech in _periodes_supplementaires(today.replace(day=28), 6):
                if date_ech <= today + timedelta(days=HORIZONS[-1]):
                    evenements.append((date_ech, -cout, "Masse salariale prévisionnelle"))

    # Événements manuels
    for evt in CashEvent.objects.filter(company=company, is_realized=False):
        montant = evt.amount * evt.probability
        if evt.is_recurring_monthly:
            for date_ech in _periodes_supplementaires(evt.expected_date, 6):
                if date_ech <= today + timedelta(days=HORIZONS[-1]):
                    evenements.append((date_ech, montant if evt.direction == "in" else -montant, evt.label))
        else:
            evenements.append((evt.expected_date, montant if evt.direction == "in" else -montant, evt.label))

    horizons = []
    for horizon in HORIZONS:
        date_cible = today + timedelta(days=horizon)
        cumul = sum(m for d, m, _ in evenements if d <= date_cible)
        horizons.append(
            {
                "jours": horizon,
                "date": date_cible.isoformat(),
                "solde_prevu": (solde_initial + cumul).quantize(CENT),
            }
        )

    return {
        "scenario": scenario,
        "definitions": {
            "point_depart": "Solde bancaire disponible à ce jour (import soldé).",
            "probabilite_encaissement": str(proba),
            "decalage_encaissements_jours": decalage,
            "sources": [
                "factures clients non soldées (reste à payer × probabilité, à l'échéance)",
                "factures fournisseurs validées non soldées (à l'échéance)",
                "abonnements actifs (échéances futures)",
                "masse salariale = coût employeur du dernier cycle (mensuel)",
                "événements de trésorerie saisis manuellement",
            ],
        },
        "solde_initial": solde_initial.quantize(CENT),
        "horizons": horizons,
        "evenements": [
            {"date": d.isoformat(), "montant": m.quantize(CENT), "libelle": l}
            for d, m, l in sorted(evenements, key=lambda e: e[0])
        ],
    }
