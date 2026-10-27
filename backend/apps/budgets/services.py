"""Pilotage budgétaire : réalisé issu de la comptabilité, seuil, BFR, coûts."""

from datetime import date
from decimal import Decimal

from django.db.models import Sum

from .models import Budget


def realise_mensuel(company, year: int, account_prefix: str) -> list[Decimal]:
    """Réalisé mensuel comptabilisé pour un préfixe de compte (classe 6/7)."""
    from apps.accounting.models import EntryLine, EntryStatus

    qs = (
        EntryLine.objects.filter(
            entry__company=company,
            entry__status__in=(EntryStatus.VALIDEE, EntryStatus.CONTRE_PASSEE),
            entry__date__year=year,
            account__number__startswith=account_prefix,
        )
        .values("entry__date__month")
        .annotate(d=Sum("debit"), c=Sum("credit"))
    )
    par_mois = {l["entry__date__month"]: (l["d"] or 0) - (l["c"] or 0) for l in qs}
    resultat = []
    for mois in range(1, 13):
        valeur = par_mois.get(mois, Decimal(0))
        # Les produits (classe 7) sont en crédit → inverser le signe
        if account_prefix.startswith("7"):
            valeur = -valeur
        resultat.append(valeur.quantize(Decimal("0.01")))
    return resultat


def budget_vs_realise(budget: Budget) -> dict:
    """Compare budget et réalisé par ligne, avec distinctions claires."""
    lignes = []
    total_budget_produits = Decimal(0)
    total_budget_charges = Decimal(0)
    total_realise_produits = Decimal(0)
    total_realise_charges = Decimal(0)
    for line in budget.lines.all():
        realise = realise_mensuel(budget.company, budget.year, line.account_prefix) if line.account_prefix else None
        prevus = [Decimal(str(v)) for v in (line.monthly_amounts or [0] * 12)]
        cumul_prevu = sum(prevus).quantize(Decimal("0.01"))
        cumul_realise = sum(realise).quantize(Decimal("0.01")) if realise else None
        nature_charge = line.nature in {"charge_fixe", "charge_variable", "masse_salariale"}
        if nature_charge:
            total_budget_charges += cumul_prevu
            if cumul_realise is not None:
                total_realise_charges += cumul_realise
        else:
            total_budget_produits += cumul_prevu
            if cumul_realise is not None:
                total_realise_produits += cumul_realise
        lignes.append(
            {
                "id": line.id,
                "label": line.label,
                "nature": line.nature,
                "account_prefix": line.account_prefix,
                "prevu_mensuel": [str(v) for v in prevus],
                "realise_mensuel": [str(v) for v in realise] if realise else None,
                "cumul_prevu": str(cumul_prevu),
                "cumul_realise": str(cumul_realise) if cumul_realise is not None else None,
                "source_realise": "comptabilite" if realise is not None else "aucune",
            }
        )
    return {
        "annee": budget.year,
        "lignes": lignes,
        "synthese": {
            "budget_produits": str(total_budget_produits),
            "budget_charges": str(total_budget_charges),
            "realise_produits": str(total_realise_produits),
            "realise_charges": str(total_realise_charges),
            "resultat_budgete": str(total_budget_produits - total_budget_charges),
            "resultat_realise": str(total_realise_produits - total_realise_charges),
        },
        "avertissement": (
            "Le réalisé est issu de la comptabilité validée ; le prévu repose "
            "sur les hypothèses documentées du budget."
        ),
    }


def seuil_de_rentabilite(budget: Budget) -> dict | None:
    """Seuil de rentabilité = CF / (1 − CV/CA prévu). Définition en docs/."""
    cf = Decimal(0)
    cv = Decimal(0)
    ca = Decimal(0)
    for line in budget.lines.all():
        total = line.total_annuel
        if line.nature == "charge_fixe":
            cf += total
        elif line.nature == "charge_variable":
            cv += total
        elif line.nature == "produit":
            ca += total
    if ca <= 0:
        return None
    taux_mcv = (ca - cv) / ca  # taux de marge sur coûts variables
    if taux_mcv <= 0:
        return {"message": "Taux de marge sur coûts variables nul ou négatif : seuil indéfinissable."}
    seuil = (cf / taux_mcv).quantize(Decimal("0.01"))
    return {
        "charges_fixes": str(cf),
        "charges_variables_prevues": str(cv),
        "chiffre_affaires_prevu": str(ca),
        "taux_marge_cout_variable": str(taux_mcv.quantize(Decimal("0.0001"))),
        "seuil_rentabilite_ht": str(seuil),
        "formule": "Seuil = charges fixes / taux de marge sur coûts variables",
    }


def besoin_fonds_roulement(company) -> dict:
    """BFR de pilotage simplifié : créances clients + stocks − dettes fournisseurs.

    Les montants s'appuient sur les soldes comptables validés (comptes 411/401/3).
    """
    from apps.accounting.models import EntryLine, EntryStatus

    def solde(prefix, sens_debiteur=True):
        agg = EntryLine.objects.filter(
            entry__company=company,
            entry__status__in=(EntryStatus.VALIDEE, EntryStatus.CONTRE_PASSEE),
            account__number__startswith=prefix,
        ).aggregate(d=Sum("debit"), c=Sum("credit"))
        valeur = (agg["d"] or Decimal(0)) - (agg["c"] or Decimal(0))
        return valeur if sens_debiteur else -valeur

    creances = solde("411")
    stocks = solde("3")
    dettes = solde("401", sens_debiteur=False)
    bfr = creances + stocks - dettes
    return {
        "creances_clients": str(creances.quantize(Decimal("0.01"))),
        "stocks": str(stocks.quantize(Decimal("0.01"))),
        "dettes_fournisseurs": str(dettes.quantize(Decimal("0.01"))),
        "bfr": str(bfr.quantize(Decimal("0.01"))),
        "definition": "BFR = créances clients + stocks − dettes fournisseurs (soldes 411, 3xx, 401).",
    }
