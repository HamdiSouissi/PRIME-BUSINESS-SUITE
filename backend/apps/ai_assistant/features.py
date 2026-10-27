"""Fonctionnalités IA de haut niveau (prompts métier contrôlés).

Chaque fonction construit un contexte limité aux données AUTORISÉES et des
instructions claires. L'IA fournit un brouillon / une synthèse : la décision
finale reste humaine (section 15 du cahier des charges).
"""

from .models import AIFeature
from .providers import generer


def resumer_document(company, texte: str, langue: str = "fr", user=None) -> dict:
    reponse = generer(
        company,
        AIFeature.RESUME_DOCUMENT,
        [
            {"role": "system", "content": (
                "Vous êtes un assistant administratif. Résumez fidèlement le "
                "document fourni, sans inventer d'information, en français. "
                "Structure : contexte, points clés, montants/dates, actions."
            )},
            {"role": "user", "content": texte[:20000]},
        ],
        user=user,
    )
    return {"resume": reponse.content, "modele": reponse.model, "nature": "proposition à relire"}


def extraire_facture(company, texte: str, user=None) -> dict:
    """Extraction structurée des champs d'une facture (JSON attendu)."""
    reponse = generer(
        company,
        AIFeature.EXTRACTION_FACTURE,
        [
            {"role": "system", "content": (
                "Extrayez les données de cette facture au format JSON strict avec les clés : "
                "fournisseur, siret, date_facture, numero, montant_ht, tva, montant_ttc, "
                "echeance, iban. Utilisez null si absent. Répondez UNIQUEMENT par le JSON."
            )},
            {"role": "user", "content": texte[:15000]},
        ],
        user=user,
    )
    return {"extraction": reponse.content, "modele": reponse.model,
            "avertissement": "Extraction à contrôler avant toute saisie."}


def brouillon_contrat(company, contexte: str, type_document: str, user=None) -> dict:
    reponse = generer(
        company,
        AIFeature.BROUILLON_CONTRAT,
        [
            {"role": "system", "content": (
                "Vous préparez un BROUILLON de document juridique en français, destiné à être "
                "produit à titre de proposition. Mentionnez explicitement [BROUILLON — relecture "
                "juridique obligatoire] en tête et n'offrez aucun conseil juridique définitif."
            )},
            {"role": "user", "content": f"Type : {type_document}\n\nContexte :\n{contexte[:15000]}"},
        ],
        user=user,
    )
    return {"brouillon": reponse.content, "modele": reponse.model,
            "statut": "brouillon_ia — validation humaine obligatoire avant usage"}


def synthese_tresorerie(company, previsionnel: dict, user=None) -> dict:
    """Explique le prévisionnel de trésorerie déjà calculé par le moteur."""
    import json

    reponse = generer(
        company,
        AIFeature.SYNTHESE_TRESORERIE,
        [
            {"role": "system", "content": (
                "Synthétisez en français la situation de trésorerie : solde, horizons, risques "
                "et points de vigilance. Interdiction d'inventer des chiffres ; commentez "
                "uniquement les données fournies et proposez des vérifications."
            )},
            {"role": "user", "content": json.dumps(previsionnel, ensure_ascii=False, default=str)[:12000]},
        ],
        user=user,
    )
    return {"synthese": reponse.content, "modele": reponse.model, "nature": "commentaire indicatif"}


def expliquer_indicateur(company, nom: str, valeur: str, definitions: str, user=None) -> dict:
    reponse = generer(
        company,
        AIFeature.EXPLICATION_INDICATEUR,
        [
            {"role": "system", "content": (
                "Expliquez cet indicateur financier en français à un dirigeant non expert : "
                "définition, lecture, points d'attention. Restez strictement factuel."
            )},
            {"role": "user", "content": f"Indicateur : {nom}\nValeur : {valeur}\nDéfinitions : {definitions[:6000]}"},
        ],
        user=user,
    )
    return {"explication": reponse.content, "modele": reponse.model}


def rediger_email(company, contexte: str, ton: str = "professionnel", user=None) -> dict:
    reponse = generer(
        company,
        AIFeature.REDACTION_EMAIL,
        [
            {"role": "system", "content": (
                f"Rédigez un e-mail professionnel en français, ton {ton}. "
                "Fournissez objet et corps. Aucune promesse contractuelle."
            )},
            {"role": "user", "content": contexte[:8000]},
        ],
        user=user,
    )
    return {"email": reponse.content, "modele": reponse.model, "nature": "brouillon"}


def classifier_depense(company, libelle: str, categories: list[str], marchand: str = "", user=None) -> dict:
    reponse = generer(
        company,
        AIFeature.CLASSIFICATION_DEPENSE,
        [
            {"role": "system", "content": (
                "Suggérez la catégorie de note de frais la plus probable parmi la liste fournie. "
                "Répondez par : code_categorie | justification courte."
            )},
            {"role": "user", "content": (
                f"Marchand : {marchand}\nLibellé : {libelle}\nCatégories : {', '.join(categories)}"
            )},
        ],
        user=user,
    )
    return {"suggestion": reponse.content, "modele": reponse.model,
            "avertissement": "Suggestion indicative — la validation reste manuelle."}


def detecter_anomalies(company, donnees: str, user=None) -> dict:
    reponse = generer(
        company,
        AIFeature.ANOMALIES,
        [
            {"role": "system", "content": (
                "Lot de données financières fourni. Signalez les anomalies probables à VÉRIFIER "
                "manuellement (doublons, montants atypiques, dates incohérentes). Pas de conclusion "
                "définitive ; proposez des pistes de contrôle."
            )},
            {"role": "user", "content": donnees[:15000]},
        ],
        user=user,
    )
    return {"anomalies_a_verifier": reponse.content, "modele": reponse.model,
            "nature": "pistes de vérification"}


def preparer_rapport(company, donnees: str, sujet: str, user=None) -> dict:
    reponse = generer(
        company,
        AIFeature.RAPPORT,
        [
            {"role": "system", "content": (
                "Préparez un rapport structuré en français (titres, synthèse, données, "
                "recommandations de vérification). Jetez uniquement à partir des données fournies."
            )},
            {"role": "user", "content": f"Sujet : {sujet}\n\nDonnées :\n{donnees[:15000]}"},
        ],
        user=user,
    )
    return {"rapport": reponse.content, "modele": reponse.model, "nature": "brouillon à valider"}
