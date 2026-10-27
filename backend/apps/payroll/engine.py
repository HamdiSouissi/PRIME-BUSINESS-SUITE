"""Moteur de calcul de paie.

Principes :
- Pur et déterministe : mêmes entrées + même jeu de règles = même résultat.
- AUCUN taux/plafond codé en dur : tout vient de `PayrollParameterSet` et de
  ses `ContributionRule`.
- Tous les montants sont arrondis au centime (ROUND_HALF_UP).

Ce moteur calcule une paie française de type « mensualisée ». Sa conformité
réglementaire doit être validée par un spécialiste de la paie : les jeux de
règles livrés sont marqués « provisoires » tant qu'un expert ne les a pas
vérifiés, ce qui bloque la validation définitive des cycles.
"""

import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def q2(value) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def compute_payslip(inputs: dict, params, rules) -> dict:
    """Calcule un bulletin à partir des variables du mois et des règles.

    inputs attendu (JSON sérialisable) :
    {
      "salaire_base": Decimal/str,          # salaire mensuel contractuel
      "primes": [{"label": str, "amount": str, "imposable": bool}],
      "retenues": [{"label": str, "amount": str}],        # absences…
      "heures_sup": [{"hours": str, "majoration": str}],  # % : 25 ou 50
      "avantages_nature": [{"label": str, "amount": str}],
      "remboursements": [{"label": str, "amount": str}],  # non imposables
      "taux_pas": str,                       # taux de prélèvement à la source
      "is_cadre": bool,
      "heures_mensuelles": str,              # durée contractuelle
    }
    """
    zero = Decimal(0)
    salaire_base = Decimal(str(inputs.get("salaire_base", "0")))
    heures_mensuelles = Decimal(
        str(inputs.get("heures_mensuelles") or params.heures_mensuelles_reference)
    )
    primes = inputs.get("primes", [])
    retenues = inputs.get("retenues", [])
    avantages = inputs.get("avantages_nature", [])
    remboursements = inputs.get("remboursements", [])
    heures_sup = inputs.get("heures_sup", [])
    taux_pas = Decimal(str(inputs.get("taux_pas", "0")))
    is_cadre = bool(inputs.get("is_cadre", False))

    taux_horaire = salaire_base / heures_mensuelles if heures_mensuelles else zero

    # --- Éléments de brut ------------------------------------------------
    lignes_brut = [
        {
            "label": "Salaire de base",
            "base": f"{heures_mensuelles}",
            "amount": q2(salaire_base),
        }
    ]
    montant_hs = zero
    hs_detail = []
    for hs in heures_sup:
        hours = Decimal(str(hs.get("hours", "0")))
        majoration = Decimal(str(hs.get("majoration", "25")))
        montant = q2(taux_horaire * hours * (1 + majoration / 100))
        montant_hs += montant
        hs_detail.append(
            {
                "label": f"Heures supplémentaires majorées à {majoration} % ({hours} h)",
                "base": f"{hours} h × {q2(taux_horaire)} €",
                "amount": montant,
            }
        )
    lignes_brut += hs_detail

    montant_primes = zero
    for prime in primes:
        montant = q2(str(prime.get("amount", "0")))
        montant_primes += montant
        lignes_brut.append(
            {"label": f"Prime : {prime.get('label', 'prime')}", "base": "", "amount": montant}
        )

    montant_avantages = zero
    for av in avantages:
        montant = q2(str(av.get("amount", "0")))
        montant_avantages += montant
        lignes_brut.append(
            {"label": f"Avantage en nature : {av.get('label', '')}", "base": "", "amount": montant}
        )

    montant_retenues = zero
    for retenue in retenues:
        montant = q2(str(retenue.get("amount", "0")))
        montant_retenues += montant
        lignes_brut.append(
            {"label": f"Retenue : {retenue.get('label', 'absence')}", "base": "", "amount": -montant}
        )

    brut = q2(salaire_base + montant_hs + montant_primes + montant_avantages - montant_retenues)

    # --- Cotisations ------------------------------------------------------
    pmss = Decimal(params.pmss_mensuel)
    tranche_a = min(brut, pmss)
    tranche_b = max(zero, brut - pmss)
    csg_base = q2(brut * Decimal(params.csg_assujettissement) / 100)

    def base_de(rule) -> Decimal:
        if rule.base_type == "brut":
            return brut
        if rule.base_type == "tranche_a":
            return tranche_a
        if rule.base_type == "tranche_b":
            return tranche_b
        if rule.base_type == "csg_base":
            return csg_base
        return brut

    def plafonne(base, rule) -> Decimal:
        multiple = Decimal(rule.ceiling_multiple or 0)
        if multiple <= 0 or rule.base_type in ("tranche_a", "tranche_b", "csg_base"):
            return base
        return min(base, pmss * multiple)

    lignes = []
    total_sal = zero
    total_pat = zero
    non_deductible_csg = zero
    patronal_taxable = zero  # part patronale de prévoyance réintégrée

    for rule in sorted(rules, key=lambda r: (r.order, r.code)):
        if not rule.is_active or not rule.applies_to(is_cadre):
            continue
        base = plafonne(base_de(rule), rule)
        if base <= 0:
            continue
        amount_sal = q2(base * Decimal(rule.rate_salarial) / 100)
        amount_pat = q2(base * Decimal(rule.rate_patronal) / 100)
        total_sal += amount_sal
        total_pat += amount_pat
        if rule.affects_net_imposable:
            non_deductible_csg += amount_sal
        if rule.patronal_part_taxable:
            patronal_taxable += amount_pat
        lignes.append(
            {
                "section": rule.section,
                "code": rule.code,
                "label": rule.label,
                "base": q2(base),
                "rate_salarial": Decimal(rule.rate_salarial),
                "amount_salarial": amount_sal,
                "rate_patronal": Decimal(rule.rate_patronal),
                "amount_patronal": amount_pat,
                "is_allegement": False,
            }
        )

    # --- Réduction générale dégressive (exonération patronale) -----------
    allegement = zero
    reduction_detail = None
    if params.reduction_generale_active and brut > 0:
        smic_mensuel = Decimal(params.smic_mensuel_35h)
        # Ajustement de la référence SMIC pour les temps partiels/complets :
        reference_smic = smic_mensuel * (heures_mensuelles / Decimal(params.heures_mensuelles_reference))
        if brut < Decimal("1.6") * reference_smic:
            t = Decimal(params.reduction_generale_t)
            coefficient = (t / Decimal("0.6")) * (Decimal("1.6") * reference_smic / brut - 1)
            coefficient = max(zero, min(coefficient, t))
            allegement = q2(brut * coefficient)
            if allegement > 0:
                lignes.append(
                    {
                        "section": "autres",
                        "code": "REDUC-GEN",
                        "label": "Réduction générale dégressive des cotisations patronales",
                        "base": brut,
                        "rate_salarial": zero,
                        "amount_salarial": zero,
                        "rate_patronal": -q2(coefficient * 100),
                        "amount_patronal": -allegement,
                        "is_allegement": True,
                    }
                )
                reduction_detail = {
                    "coefficient": str(coefficient.normalize()),
                    "montant": str(allegement),
                }

    total_sal = q2(total_sal)
    total_pat_brut = q2(total_pat)
    total_pat_net = q2(total_pat - allegement)

    # --- Nets -------------------------------------------------------------
    net_social = q2(brut - total_sal)
    net_imposable = q2(net_social + non_deductible_csg + patronal_taxable)
    pas = q2(net_imposable * taux_pas / 100)

    montant_remboursements = zero
    for remb in remboursements:
        montant_remboursements += q2(str(remb.get("amount", "0")))

    net_a_payer_avant_impot = q2(net_social + montant_remboursements)
    net_a_payer = q2(net_a_payer_avant_impot - pas)
    cout_employeur = q2(brut + total_pat_net)

    result = {
        "lignes_brut": lignes_brut,
        "remboursements": [
            {"label": r.get("label", "Remboursement"), "amount": q2(str(r.get("amount", "0")))}
            for r in remboursements
        ],
        "cotisations": lignes,
        "totaux": {
            "brut": brut,
            "tranche_a": q2(tranche_a),
            "tranche_b": q2(tranche_b),
            "assiette_csg": csg_base,
            "total_cotisations_salariales": total_sal,
            "total_cotisations_patronales_brutes": total_pat_brut,
            "allegements": allegement,
            "total_cotisations_patronales": total_pat_net,
            "net_social": net_social,
            "net_imposable": net_imposable,
            "taux_pas": taux_pas,
            "prelevement_a_la_source": pas,
            "net_a_payer_avant_impot": net_a_payer_avant_impot,
            "net_a_payer": net_a_payer,
            "cout_employeur": cout_employeur,
        },
        "reduction_generale": reduction_detail,
    }
    return _jsonable(result)


def _jsonable(obj):
    """Convertit récursivement les Decimal en str (JSON strict, sans perte)."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def hash_result(result: dict) -> str:
    """Empreinte d'intégrité du résultat (détection de modification)."""
    payload = json.dumps(result, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()
