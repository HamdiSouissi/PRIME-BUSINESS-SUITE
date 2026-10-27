"""Génération des échéances, catalogue de référence et tableau de bord."""

from datetime import date, timedelta

from django.db import transaction

from .models import ObligationDefinition, ObligationInstance, Periodicity

# ---------------------------------------------------------------------------
# Catalogue de référence (sources officielles, dates de vérification)
# ⚠️ Les dates indiquées sont les échéances USUELLES : chaque entreprise les
# vérifie (montant, modalités) auprès de l'administration concernée.
# ---------------------------------------------------------------------------

CATALOGUE = [
    {
        "code": "DSN-MENSUELLE",
        "label": "Déclaration Sociale Nominative (mensuelle)",
        "category": "sociale",
        "periodicity": "mensuelle",
        "due_day": 15,
        "description": (
            "DSN mensuelle, en principe le 15 du mois suivant l'emploi des salariés "
            "(le 5 pour certaines entreprises selon le mode de dépôt)."
        ),
        "applicability": {"headcount_min": 1},
        "source_url": "https://www.net-entreprises.fr/",
        "source_label": "net-entreprises — DSN",
    },
    {
        "code": "URSSAF-COTISATIONS",
        "label": "Paiement des cotisations sociales",
        "category": "sociale",
        "periodicity": "mensuelle",
        "due_day": 15,
        "description": "Paiement des cotisations (suite de la DSN mensuelle).",
        "applicability": {"headcount_min": 1},
        "source_url": "https://www.urssaf.fr/",
        "source_label": "URSSAF — échéances",
    },
    {
        "code": "TVA-CA12",
        "label": "Déclaration de TVA (CA12 — régime réel simplifié)",
        "category": "fiscale",
        "periodicity": "annuelle",
        "due_day": 3,
        "due_month": 5,
        "description": "Déclaration annuelle CA12, début mai (télédéclaration).",
        "applicability": {"vat_regimes": ["reel_simplifie"]},
        "source_url": "https://www.impots.gouv.fr/professionnel/mes-acheances",
        "source_label": "impots.gouv.fr — TVA régime simplifié",
    },
    {
        "code": "TVA-CA3",
        "label": "Déclaration de TVA CA3 (régime réel normal)",
        "category": "fiscale",
        "periodicity": "mensuelle",
        "due_day": 19,
        "description": "Déclaration mensuelle CA3 (date variable selon département).",
        "applicability": {"vat_regimes": ["reel_normal"]},
        "source_url": "https://www.impots.gouv.fr/",
        "source_label": "DGFiP — TVA réel normal",
    },
    {
        "code": "LIASSE-FISCALE",
        "label": "Liasse fiscale et acomptes d'IS",
        "category": "fiscale",
        "periodicity": "annuelle",
        "due_day": 3,
        "due_month": 5,
        "description": (
            "Déclaration de résultat dans les 3 mois (télédéclaration) suivant la "
            "clôture pour un exercice au 31/12. Adapter selon la date de clôture."
        ),
        "applicability": {"legal_forms": ["sasu", "sas", "eurl", "sarl", "sa"]},
        "source_url": "https://www.impots.gouv.fr/",
        "source_label": "DGFiP — résultats sociétés",
    },
    {
        "code": "AG-APPROBATION",
        "label": "Assemblée générale d'approbation des comptes",
        "category": "comptable",
        "periodicity": "annuelle",
        "due_day": 30,
        "due_month": 6,
        "description": (
            "Approbation des comptes dans les 6 mois de la clôture (sociétés). "
            "Date indicative pour une clôture au 31/12."
        ),
        "applicability": {"legal_forms": ["sasu", "sas", "eurl", "sarl", "sa"]},
        "source_url": "https://www.legifrance.gouv.fr/",
        "source_label": "Code de commerce (approbation des comptes)",
    },
    {
        "code": "DEPOT-COMPTES",
        "label": "Dépôt des comptes annuels au greffe",
        "category": "comptable",
        "periodicity": "annuelle",
        "due_day": 30,
        "due_month": 7,
        "description": "Dépôt dans le délai légal suivant l'approbation des comptes.",
        "applicability": {"legal_forms": ["sasu", "sas", "eurl", "sarl", "sa"]},
        "source_url": "https://www.infogreffe.fr/",
        "source_label": "Infogreffe — dépôt des comptes",
    },
    {
        "code": "CFE",
        "label": "Cotisation foncière des entreprises (CFE)",
        "category": "fiscale",
        "periodicity": "annuelle",
        "due_day": 15,
        "due_month": 12,
        "description": "Paiement de la CFE, en principe le 15 décembre.",
        "applicability": {},
        "source_url": "https://www.impots.gouv.fr/",
        "source_label": "DGFiP — CFE",
    },
    {
        "code": "CONSERVE-BULLETINS",
        "label": "Conservation des bulletins de paie (5 ans)",
        "category": "documentaire",
        "periodicity": "ponctuelle",
        "due_day": 31,
        "due_month": 12,
        "description": (
            "Conservation des bulletins, contrats et pièces sociales : durées "
            "légales variables (5 ans pour les bulletins en double exemplaire)."
        ),
        "applicability": {"headcount_min": 1},
        "source_url": "https://www.service-public.fr/",
        "source_label": "Service-Public — conservation des documents",
    },
]


@transaction.atomic
def initialiser_catalogue():
    """Crée/met à jour le catalogue de référence des obligations (idempotent)."""
    for item in CATALOGUE:
        ObligationDefinition.objects.update_or_create(
            code=item["code"], defaults={**item, "verified_at": date(2025, 1, 1)}
        )


def prochain_occurrence(definition: ObligationDefinition, depuis: date) -> date | None:
    """Calcule la prochaine date d'échéance selon la périodicité."""
    if definition.periodicity == Periodicity.MENSUELLE:
        candidate = depuis.replace(day=min(definition.due_day, 28))
        if candidate <= depuis:
            month = depuis.month + 1
            year = depuis.year + (1 if month > 12 else 0)
            month = month if month <= 12 else 1
            candidate = date(year, month, min(definition.due_day, 28))
        return candidate
    if definition.periodicity == Periodicity.TRIMESTRIELLE:
        for decalage in range(0, 13):
            mois = (depuis.month - 1 + decalage) % 12 + 1
            annee = depuis.year + (depuis.month - 1 + decalage) // 12
            if mois % 3 == 0:
                candidate = date(annee, mois, min(definition.due_day, 28))
                if candidate > depuis:
                    return candidate
        return None
    if definition.periodicity in {Periodicity.ANNUELLE, Periodicity.SEMESTRIELLE, Periodicity.PONCTUELLE}:
        mois = definition.due_month or 12
        candidate = date(depuis.year, mois, definition.due_day)
        if candidate <= depuis:
            candidate = date(depuis.year + 1, mois, definition.due_day)
        return candidate
    return None


@transaction.atomic
def generer_instances(company, jusqu_au: date | None = None) -> int:
    """Génère les prochaines instances applicables à l'entreprise (idempotent)."""
    jusqu_au = jusqu_au or date.today() + timedelta(days=120)
    count = 0
    for definition in ObligationDefinition.objects.filter(active=True):
        if not definition.is_applicable_to(company):
            continue
        prochaine = prochain_occurrence(definition, date.today())
        while prochaine and prochaine <= jusqu_au:
            _, created = ObligationInstance.objects.get_or_create(
                company=company, definition=definition, due_date=prochaine
            )
            count += 1 if created else 0
            prochaine = prochain_occurrence(definition, prochaine)
    # Marque les obligations dépassées
    ObligationInstance.objects.filter(
        company=company, status__in=("a_faire", "en_cours"), due_date__lt=date.today()
    ).update(status="depassee")
    return count


def tableau_de_bord(company) -> dict:
    generer_instances(company)
    instances = ObligationInstance.objects.filter(company=company).select_related("definition")
    a_faire = instances.filter(status="a_faire", due_date__gte=date.today()).order_by("due_date")
    depassees = instances.filter(status="depassee").order_by("due_date")
    a_venir_30j = a_faire.filter(due_date__lte=date.today() + timedelta(days=30))
    return {
        "a_faire": [
            {
                "id": i.id,
                "label": i.definition.label,
                "category": i.definition.category,
                "due_date": i.due_date.isoformat(),
                "status": i.status,
                "source": i.definition.source_url,
                "verifiee_le": i.definition.verified_at.isoformat() if i.definition.verified_at else None,
                "days_late": i.days_late,
            }
            for i in (list(depassees) + list(a_venir_30j))
        ],
        "compteurs": {
            "a_faire": a_faire.count(),
            "depassees": depassees.count(),
            "faites_ce_mois": instances.filter(
                status="faite",
                completed_at__year=date.today().year,
                completed_at__month=date.today().month,
            ).count(),
        },
        "avertissement": (
            "Calendrier indicatif fondé sur le catalogue configuré. Les dates "
            "réelles dépendent de la situation de l'entreprise (département, "
            "effectif, mode de déclaration) : vérifiez chaque source officielle."
        ),
    }
