"""Plan comptable général (PCG) — sous-ensemble de démarrage.

Le plan est paramétrable : ces comptes servent de base et peuvent être
complétés / renommés selon le référentiel applicable à l'entreprise.
"""

JOURNAUX = [
    ("VE", "Journal des ventes", "ventes"),
    ("AC", "Journal des achats", "achats"),
    ("BQ", "Journal de banque", "banque"),
    ("PAIE", "Journal de paie", "paie"),
    ("OD", "Opérations diverses", "od"),
]

COMPTES = [
    # numéro, intitulé, classe, type
    ("101000", "Capital", "1", "general"),
    ("108000", "Compte de l'exploitant / associé", "1", "general"),
    ("110000", "Report à nouveau", "1", "general"),
    ("120000", "Résultat de l'exercice", "1", "general"),
    ("164000", "Emprunts divers", "1", "general"),
    ("164200", "Emprunts bancaires", "1", "general"),
    ("168000", "Comptes courants d'associés", "1", "general"),
    ("205000", "Concessions, brevets, logiciels", "2", "general"),
    ("207000", "Fonds commercial", "2", "general"),
    ("218300", "Matériel informatique", "2", "general"),
    ("218200", "Matériel de transport", "2", "general"),
    ("281830", "Amortissements du matériel informatique", "2", "general"),
    ("281820", "Amortissements du matériel de transport", "2", "general"),
    ("401000", "Fournisseurs", "4", "fournisseur"),
    ("404000", "Fournisseurs d'immobilisations", "4", "fournisseur"),
    ("408100", "Fournisseurs — factures non parvenues", "4", "fournisseur"),
    ("411000", "Clients", "4", "client"),
    ("418100", "Clients — factures à établir", "4", "client"),
    ("421000", "Personnel — rémunérations dues", "4", "general"),
    ("425000", "Personnel — avances et acomptes", "4", "general"),
    ("431000", "URSSAF", "4", "general"),
    ("437000", "Autres organismes sociaux", "4", "general"),
    ("444100", "État — impôt sur les sociétés", "4", "general"),
    ("444510", "État — prélèvement à la source", "4", "general"),
    ("445510", "TVA à décaisser", "4", "general"),
    ("445660", "TVA déductible sur autres biens et services", "4", "general"),
    ("445670", "Crédit de TVA à reporter", "4", "general"),
    ("445710", "TVA collectée", "4", "general"),
    ("446900", "État — autres comptes créditeurs", "4", "general"),
    ("455000", "Associés — comptes courants", "4", "general"),
    ("457000", "Associés — dividendes à payer", "4", "general"),
    ("486000", "Charges constatées d'avance", "4", "general"),
    ("487000", "Produits constatés d'avance", "4", "general"),
    ("512000", "Banque", "5", "banque"),
    ("530000", "Caisse", "5", "caisse"),
    ("580000", "Virements internes", "5", "general"),
    ("603100", "Achats de marchandises", "6", "general"),
    ("606100", "Fournitures non stockables", "6", "general"),
    ("606300", "Fournitures d'entretien", "6", "general"),
    ("613200", "Locations immobilières", "6", "general"),
    ("614000", "Frais d'étude et de documentation", "6", "general"),
    ("615000", "Entretien et réparations", "6", "general"),
    ("622600", "Honoraires", "6", "general"),
    ("623000", "Publicité et marketing", "6", "general"),
    ("625100", "Déplacements", "6", "general"),
    ("625700", "Réceptions et repas d'affaires", "6", "general"),
    ("626000", "Frais postaux et télécommunications", "6", "general"),
    ("627000", "Services bancaires", "6", "general"),
    ("631000", "Impôts, taxes sur rémunérations", "6", "general"),
    ("635000", "Impôts et taxes (autres)", "6", "general"),
    ("641100", "Salaires, appointements", "6", "general"),
    ("641400", "Indemnités et avantages divers", "6", "general"),
    ("645100", "URSSAF (cotisations patronales)", "6", "general"),
    ("645300", "Caisses de retraite", "6", "general"),
    ("661100", "Intérêts des emprunts", "6", "general"),
    ("671000", "Charges exceptionnelles", "6", "general"),
    ("681120", "Dotations aux amortissements", "6", "general"),
    ("695000", "Impôts sur les bénéfices", "6", "general"),
    ("706000", "Prestations de services", "7", "general"),
    ("706100", "Abonnements et revenus récurrents", "7", "general"),
    ("707000", "Ventes de marchandises", "7", "general"),
    ("708000", "Produits des activités annexes", "7", "general"),
    ("761000", "Produits financiers", "7", "general"),
    ("771000", "Produits exceptionnels", "7", "general"),
    ("775000", "Produits des cessions d'immobilisations", "7", "general"),
]


def peupler_plan_comptable(company):
    """Crée les journaux et comptes de base pour une entreprise (idempotent)."""
    from .models import Account, Journal

    for code, label, jtype in JOURNAUX:
        Journal.objects.get_or_create(
            company=company, code=code, defaults={"label": label, "journal_type": jtype}
        )
    for number, label, classe, ctype in COMPTES:
        Account.objects.get_or_create(
            company=company, number=number,
            defaults={"label": label, "account_class": classe, "account_type": ctype},
        )
