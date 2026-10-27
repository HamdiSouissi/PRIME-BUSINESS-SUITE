"""Services comptables : création, validation, contre-passation, rapports."""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.exceptions import BusinessError
from apps.core.models import Sequence

from .models import Account, EntryLine, EntryStatus, FiscalYear, Journal, JournalEntry


def _exercice_ouvert(company, date_valeur: date):
    fy = FiscalYear.pour_date(company, date_valeur)
    if fy is None:
        raise BusinessError(
            f"Aucun exercice comptable ne couvre le {date_valeur}. Créez l'exercice.",
            code="pas_d_exercice",
        )
    if fy.status == "cloture":
        raise BusinessError(
            "Exercice clôturé : écritures interdites.", code="exercice_cloture"
        )
    if fy.status == "verrouille" and date_valeur <= fy.end_date:
        # Verrouillage : seules les écritures d'inventaire pourront être débloquées manuellement
        raise BusinessError(
            "Exercice verrouillé : déverrouillez-le pour comptabiliser.", code="exercice_verrouille"
        )
    return fy


@transaction.atomic
def creer_ecriture(company, journal_code: str, date_valeur: date, label: str,
                   lignes: list[dict], user=None, valider: bool = True,
                   source: tuple[str, str, str] | None = None) -> JournalEntry:
    """Crée (et valide) une écriture équilibrée.

    lignes : [{"account": "411000", "label": "...", "debit": x, "credit": y,
               "auxiliary": "Client X"}]
    """
    _exercice_ouvert(company, date_valeur)
    journal = Journal.objects.filter(company=company, code=journal_code).first()
    if journal is None:
        raise BusinessError(f"Journal inconnu : {journal_code}.", code="journal_inconnu")
    if not lignes:
        raise BusinessError("Écriture sans lignes.", code="sans_lignes")

    total_debit = sum(Decimal(str(l.get("debit", 0))) for l in lignes)
    total_credit = sum(Decimal(str(l.get("credit", 0))) for l in lignes)
    if total_debit != total_credit:
        raise BusinessError(
            f"Écriture non équilibrée : débit {total_debit} ≠ crédit {total_credit}.",
            code="ecriture_desquilibree",
        )
    if total_debit == 0:
        raise BusinessError("Écriture à zéro : rien à comptabiliser.", code="montant_nul")

    entry = JournalEntry(
        company=company, journal=journal, date=date_valeur, label=label,
        created_by=user,
    )
    if source:
        entry.source_model, entry.source_id, entry.source_label = source
    entry.reference = Sequence.allocate(
        company, key=f"journal:{journal_code}", prefix=f"{journal_code}-",
        year=date_valeur.year, padding=6,
    )
    if valider:
        entry.status = EntryStatus.VALIDEE
        entry.validated_by = user
        entry.validated_at = timezone.now()
    entry.save()

    for ligne in lignes:
        account = Account.objects.filter(company=company, number=ligne["account"]).first()
        if account is None:
            raise BusinessError(
                f"Compte {ligne['account']} inexistant au plan comptable.", code="compte_inconnu"
            )
        EntryLine.objects.create(
            entry=entry,
            account=account,
            label=ligne.get("label", label),
            auxiliary=ligne.get("auxiliary", ""),
            debit=Decimal(str(ligne.get("debit", 0))),
            credit=Decimal(str(ligne.get("credit", 0))),
        )
    return entry


@transaction.atomic
def valider_ecriture(entry: JournalEntry, user) -> JournalEntry:
    if entry.status != EntryStatus.BROUILLON:
        raise BusinessError("Écriture déjà validée.", code="transition_interdite")
    _exercice_ouvert(entry.company, entry.date)
    if entry.total_debit != entry.total_credit:
        raise BusinessError("Écriture non équilibrée.", code="ecriture_desquilibree")
    entry.status = EntryStatus.VALIDEE
    entry.validated_by = user
    entry.validated_at = timezone.now()
    entry.save(update_fields=["status", "validated_by", "validated_at", "updated_at"])
    return entry


@transaction.atomic
def contre_passer(entry: JournalEntry, user, date_valeur: date | None = None,
                  motif: str = "") -> JournalEntry:
    """Contre-passation : crée l'écriture inverse, sans toucher l'originale."""
    if entry.status != EntryStatus.VALIDEE:
        raise BusinessError(
            "Seule une écriture validée peut être contre-passée.", code="transition_interdite"
        )
    date_valeur = date_valeur or timezone.localdate()
    lignes = [
        {
            "account": line.account.number,
            "label": f"Extourne : {line.label}",
            "debit": line.credit,
            "credit": line.debit,
            "auxiliary": line.auxiliary,
        }
        for line in entry.lines.all()
    ]
    reverse = creer_ecriture(
        entry.company, entry.journal.code, date_valeur,
        f"Extourne {entry.reference} — {motif or entry.label}",
        lignes, user=user, valider=True,
        source=("accounting.JournalEntry", str(entry.id), f"Extourne de {entry.reference}"),
    )
    reverse.reverses = entry
    reverse.save(update_fields=["reverses"])
    entry.status = EntryStatus.CONTRE_PASSEE
    entry.save(update_fields=["status", "updated_at"])
    return reverse


# ---------------------------------------------------------------------------
# Rapports
# ---------------------------------------------------------------------------

def balance_generale(company, fy: FiscalYear | None = None) -> list[dict]:
    """Balance générale des comptes sur un exercice."""
    qs = EntryLine.objects.filter(entry__company=company, entry__status__in=(
        EntryStatus.VALIDEE, EntryStatus.CONTRE_PASSEE))
    if fy is not None:
        qs = qs.filter(entry__date__gte=fy.start_date, entry__date__lte=fy.end_date)
    lignes = (
        qs.values("account__number", "account__label")
        .annotate(total_debit=Sum("debit"), total_credit=Sum("credit"))
        .order_by("account__number")
    )
    return [
        {
            "number": l["account__number"],
            "label": l["account__label"],
            "debit": l["total_debit"] or Decimal(0),
            "credit": l["total_credit"] or Decimal(0),
            "solde": (l["total_debit"] or 0) - (l["total_credit"] or 0),
        }
        for l in lignes
    ]


def compte_de_resultat(company, fy: FiscalYear | None = None) -> dict:
    """Compte de résultat simplifié : charges (6), produits (7), résultat."""
    balance = balance_generale(company, fy)
    charges = [l for l in balance if l["number"].startswith("6")]
    produits = [l for l in balance if l["number"].startswith("7")]
    # Soldes : compte de charge positif en débit ; compte de produit négatif (crédit).
    total_charges = sum(l["solde"] for l in charges)
    total_produits = sum(-l["solde"] for l in produits)
    return {
        "charges": [{"number": c["number"], "label": c["label"], "montant": c["solde"]} for c in charges],
        "produits": [{"number": p["number"], "label": p["label"], "montant": -p["solde"]} for p in produits],
        "total_charges": total_charges,
        "total_produits": total_produits,
        "resultat": total_produits - total_charges,
    }


def bilan_simplifie(company, fy: FiscalYear | None = None) -> dict:
    """Bilan simplifié à visée de pilotage.

    ACTIF : solde débiteur des classes 2 (immobilisé), 3 (stocks), 4 débiteur
    (clients) et 5 débiteur (banque).
    PASSIF : classes 1 (capitaux), 4 créditeur (fournisseurs/dettes), 5
    créditeur (découverts), plus le résultat de l'exercice.
    """
    balance = balance_generale(company, fy)
    is_resultat = compte_de_resultat(company, fy)["resultat"]
    actif = {"immobilise": Decimal(0), "stocks": Decimal(0), "creances": Decimal(0), "disponibilites": Decimal(0)}
    passif = {"capitaux": Decimal(0), "dettes": Decimal(0), "tresorerie_passif": Decimal(0)}
    for ligne in balance:
        solde = ligne["solde"]
        numero = ligne["number"]
        if numero.startswith("2") and solde > 0:
            actif["immobilise"] += solde
        elif numero.startswith("3") and solde > 0:
            actif["stocks"] += solde
        elif numero.startswith("4") and solde > 0:
            actif["creances"] += solde
        elif numero.startswith("4") and solde < 0:
            passif["dettes"] += -solde
        elif numero.startswith("5") and solde > 0:
            actif["disponibilites"] += solde
        elif numero.startswith("5") and solde < 0:
            passif["tresorerie_passif"] += -solde
        elif numero.startswith("1") and solde < 0:
            passif["capitaux"] += -solde
    passif["resultat"] = is_resultat
    total_actif = sum(actif.values())
    total_passif = sum(v for k, v in passif.items())
    return {
        "actif": actif, "passif": passif,
        "total_actif": total_actif, "total_passif": total_passif,
        "ecart": total_actif - total_passif,
    }


def export_fec(company, fy: FiscalYear) -> str:
    """Export CSV de préparation pour l'expert-comptable.

    Format inspiré du Fichier des Écritures Comptables (colonnes usuelles) —
    la conformité formelle doit être validée avec l'expert-comptable.
    """
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="|", lineterminator="\r\n")
    writer.writerow([
        "JournalCode", "JournalLib", "EcritureNum", "EcritureDate", "CompteNum",
        "CompteLib", "CompAuxNum", "CompAuxLib", "PieceRef", "PieceDate",
        "EcritureLib", "Debit", "Credit", "EcritureLet", "DateLet",
        "ValidDate", "Montantdevise", "Idevise",
    ])
    entrees = JournalEntry.objects.filter(
        company=company,
        date__gte=fy.start_date,
        date__lte=fy.end_date,
        status__in=(EntryStatus.VALIDEE, EntryStatus.CONTRE_PASSEE),
    ).prefetch_related("lines__account", "journal")
    for entry in entrees:
        for line in entry.lines.all():
            writer.writerow([
                entry.journal.code,
                entry.journal.label,
                entry.reference,
                entry.date.strftime("%Y%m%d"),
                line.account.number,
                line.account.label,
                "",
                line.auxiliary,
                entry.source_id or entry.reference,
                entry.date.strftime("%Y%m%d"),
                line.label or entry.label,
                str(line.debit).replace(".", ","),
                str(line.credit).replace(".", ","),
                "", "",
                entry.date.strftime("%Y%m%d"),
                "", "",
            ])
    return buffer.getvalue()
