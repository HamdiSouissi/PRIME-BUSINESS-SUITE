"""Pont paie → comptabilité : écriture mensuelle du journal de paie.

Schéma de comptabilisation (simplifié, à faire valider par l'expert-comptable) :
- 641100 Salaires bruts (débit du brut total)
- 645100 Cotisations patronales (débit)
- 431000 Organismes sociaux (crédit : cotisations salariales + patronales)
- 444510 État — prélèvement à la source (crédit)
- 421000 Personnel — rémunérations dues (crédit du net à payer)
"""

from decimal import Decimal

from django.db import models as dj_models
from django.db import transaction

from apps.accounting.services import creer_ecriture
from apps.core.exceptions import BusinessError

from .models import Payslip, PayrollRun, RunStatus


@transaction.atomic
def comptabiliser_cycle(run: PayrollRun, user):
    """Génère l'écriture de paie du cycle (journal PAIE), validée."""
    if run.status not in {RunStatus.VALIDE, RunStatus.CLOTURE}:
        raise BusinessError(
            "Seul un cycle validé (définitif) est comptabilisable.", code="transition_interdite"
        )
    totaux = Payslip.objects.filter(run=run).aggregate(
        brut=dj_models.Sum("brut"),
        cotis_sal=dj_models.Sum("total_cotisations_salariales"),
        cotis_pat=dj_models.Sum("total_cotisations_patronales"),
        pas=dj_models.Sum("prelevement_a_la_source"),
        net=dj_models.Sum("net_a_payer"),
    )
    brut = totaux["brut"] or Decimal(0)
    cotis_sal = totaux["cotis_sal"] or Decimal(0)
    cotis_pat = totaux["cotis_pat"] or Decimal(0)
    pas = totaux["pas"] or Decimal(0)
    net = totaux["net"] or Decimal(0)
    if brut == 0:
        raise BusinessError("Cycle sans bulletin : rien à comptabiliser.", code="cycle_vide")

    lignes = [
        {"account": "641100", "label": f"Salaires bruts {run.month}/{run.year}", "debit": brut, "credit": 0},
        {"account": "645100", "label": f"Cotisations patronales {run.month}/{run.year}",
         "debit": cotis_pat, "credit": 0},
        {"account": "431000", "label": f"Cotisations {run.month}/{run.year}",
         "debit": 0, "credit": cotis_sal + cotis_pat},
        {"account": "444510", "label": f"Prélèvement à la source {run.month}/{run.year}",
         "debit": 0, "credit": pas},
        {"account": "421000", "label": f"Net à payer {run.month}/{run.year}",
         "debit": 0, "credit": net},
    ]
    from datetime import date
    import calendar

    dernier_jour = calendar.monthrange(run.year, run.month)[1]
    return creer_ecriture(
        run.company, "PAIE", date(run.year, run.month, dernier_jour),
        f"Paie {run.month:02d}/{run.year}", lignes, user=user, valider=True,
        source=("payroll.PayrollRun", str(run.id), f"Paie {run.month:02d}/{run.year}"),
    )
