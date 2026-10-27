"""Préparation des données DSN (Déclaration Sociale Nominative).

⚠️ STATUT HONNÊTE : ce module PRODUIT un export structuré de PREPARATION.
Il ne transmet rien et ne prétend pas être conforme au format réglementaire
net-entreprises. La DSN réelle exige :
  - le format normé publié par la DSS/net-entreprises (norme en vigueur) ;
  - l'envoi via le dispositif officiel ou un prestataire habilité ;
  - le suivi des retours (accusés, anomalies).
Les modèles DSNExport portent la preuve de transmission réelle quand une
intégration sera branchée.
"""

import json

from django.core.files.base import ContentFile

from .models import DSNExport, PayrollRun


def preparer_dsn(run: PayrollRun, user) -> DSNExport:
    """Construit un paquet de données DSN de préparation pour le cycle."""
    company = run.company
    payload = {
        "avertissement": (
            "Fichier de PREPARATION interne — n'est PAS un fichier DSN "
            "réglementaire et n'a pas été transmis à net-entreprises."
        ),
        "declarant": {
            "raison_sociale": company.name,
            "siret": company.siret,
            "naf": company.naf_code,
        },
        "periode": {"annee": run.year, "mois": run.month},
        "individus": [
            {
                "matricule": bulletin.employee.matricule,
                "nom": bulletin.employee.last_name,
                "prenom": bulletin.employee.first_name,
                "nir": bulletin.employee.social_security_number,
                "brut": str(bulletin.brut),
                "net_social": str(bulletin.net_social),
                "net_imposable": str(bulletin.net_imposable),
                "prelevement_a_la_source": str(bulletin.prelevement_a_la_source),
                "cotisations": [
                    {
                        "code": line.code,
                        "base": str(line.base),
                        "taux_salarial": str(line.rate_salarial),
                        "montant_salarial": str(line.amount_salarial),
                        "taux_patronal": str(line.rate_patronal),
                        "montant_patronal": str(line.amount_patronal),
                    }
                    for line in bulletin.lines.all()
                ],
            }
            for bulletin in run.payslips.select_related("employee").prefetch_related("lines")
        ],
    }
    export = DSNExport.objects.create(company=run.company, run=run, generated_by=user)
    export.file.save(
        f"dsn-preparation-{run.year}-{run.month:02d}.json",
        ContentFile(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")),
    )
    return export
