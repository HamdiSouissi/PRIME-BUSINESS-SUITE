"""Crée un jeu de DONNÉES DE DÉMONSTRATION pour Prime Vision Solutions.

Usage : python manage.py seed_demo [--password X]

⚠️ EXCLUSIVEMENT pour le développement et la démonstration. Les identifiants
créés sont documentés dans le README ; changez-les en production.
"""

import os
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import CompanyMembership, User
from apps.accounting.models import FiscalYear
from apps.accounting.seed_pcg import peupler_plan_comptable
from apps.ai_assistant.models import AIProvider, ProviderKind
from apps.compliance.services import generer_instances, initialiser_catalogue
from apps.contracts.models import DocumentTemplate, TemplateType
from apps.dividends.models import Associate
from apps.expenses.models import ExpenseCategory
from apps.hr.models import Contract, Employee, LeaveBalance, LeaveType
from apps.invoicing.models import Client, Supplier
from apps.core.permissions import Roles
from apps.organization.models import Company
from apps.payroll.services import creer_ruleset_reference
from apps.subscriptions.models import Periodicity, Subscription
from apps.treasury.models import BankAccount


class Command(BaseCommand):
    help = "Initialise un jeu de données de démonstration (dev uniquement)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=os.environ.get("DEMO_PASSWORD", "PrimeBDD-2026!"),
            help="Mot de passe des comptes de démonstration (à personnaliser).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        self.stdout.write("Création de l'entreprise de démonstration…")
        company, _ = Company.objects.get_or_create(
            siret="90812345600012",
            defaults={
                "name": "Prime Vision Solutions",
                "legal_form": "sas",
                "address": "12 rue de l'Innovation",
                "postal_code": "75011",
                "city": "Paris",
                "country": "France",
                "email": "contact@primevision.example",
                "phone": "+33 1 84 00 00 00",
                "siren": "908123456",
                "vat_number": "FR44908123456",
                "rcs_city": "Paris",
                "rcs_number": "908 123 456",
                "naf_code": "6201Z",
                "share_capital": Decimal("10000"),
                "currency": "EUR",
                "vat_regime": "reel_normal",
                "fiscal_year_start_month": 1,
                "bank_iban": "FR7612345678901234567890123",
                "bank_bic": "AGRIFRPPXXX",
                "bank_name": "Banque de démonstration",
                "collective_agreement": "Convention collective nationale des bureaux d'études techniques (Syntec)",
                "collective_agreement_idcc": "1486",
                "headcount": 4,
                "accountant_name": "Cabinet Fidexpert",
                "accountant_email": "contact@fidexpert.example",
                "invoice_footer": "Prime Vision Solutions — SAS au capital de 10 000 €",
            },
        )

        # --- Utilisateurs ---------------------------------------------------
        utilisateurs = [
            ("admin", Roles.ADMIN, "admin@primevision.example", "Adélaïde", "Admin"),
            ("direction", Roles.DIRECTION, "direction@primevision.example", "David", "Dirigeant"),
            ("rh", Roles.RH, "rh@primevision.example", "Rachida", "Rousseau"),
            ("paie", Roles.PAIE, "paie@primevision.example", "Paul", "Payeur"),
            ("comptable", Roles.COMPTABLE, "comptable@primevision.example", "Claire", "Compte"),
            ("finance", Roles.FINANCE, "finance@primevision.example", "Farid", "Finance"),
            ("manager", Roles.MANAGER, "manager@primevision.example", "Maya", "Manager"),
        ]
        for username, role, email, first, last in utilisateurs:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": username,
                    "first_name": first,
                    "last_name": last,
                    "is_staff": role == Roles.ADMIN,
                    "is_superuser": role == Roles.ADMIN,
                },
            )
            if created:
                user.set_password(password)
                user.save()
            CompanyMembership.objects.get_or_create(user=user, company=company, defaults={"role": role})

        admin = User.objects.get(email="admin@primevision.example")

        # --- Salariés liés ---------------------------------------------------
        salarie_user, created = User.objects.get_or_create(
            email="salarie@primevision.example",
            defaults={"username": "salarie", "first_name": "Sonia", "last_name": "Salarié"},
        )
        if created:
            salarie_user.set_password(password)
            salarie_user.save()
        CompanyMembership.objects.get_or_create(user=salarie_user, company=company,
                                                defaults={"role": Roles.SALARIE})

        # --- Comptabilité : plan PCG + exercice -------------------------------
        peupler_plan_comptable(company)
        for annee in (date.today().year - 1, date.today().year):
            FiscalYear.objects.get_or_create(
                company=company,
                start_date=date(annee, 1, 1),
                end_date=date(annee, 12, 31),
                defaults={"status": "ouvert"},
            )

        # --- RH ---------------------------------------------------------------
        cp, _ = LeaveType.objects.get_or_create(
            company=company, code="CP", defaults={"label": "Congés payés", "annual_days": 25}
        )
        rtt, _ = LeaveType.objects.get_or_create(
            company=company, code="RTT", defaults={"label": "RTT", "annual_days": 10}
        )
        LeaveType.objects.get_or_create(
            company=company, code="MAL", defaults={"label": "Absence maladie", "annual_days": 0}
        )

        employes_data = [
            {
                "matricule": "E001", "first": "David", "last": "Dirigeant", "poste": "Présidente",
                "salaire": Decimal("6500.00"), "cadre": True, "classification": "Cadre 3.3",
                "pas": Decimal("14.5"), "telephone": "+33 6 01 02 03 04",
            },
            {
                "matricule": "E002", "first": "Sonia", "last": "Salarié", "poste": "Développeuse senior",
                "salaire": Decimal("3800.00"), "cadre": True, "classification": "Cadre 2.1",
                "pas": Decimal("9.0"), "user": salarie_user,
            },
            {
                "matricule": "E003", "first": "Nolan", "last": "Noncadre", "poste": "Technicien support",
                "salaire": Decimal("2500.00"), "cadre": False, "classification": "ETAM TAM 3",
                "pas": Decimal("6.5"),
            },
            {
                "matricule": "E004", "first": "Alice", "last": "Alternante", "poste": "Alternante webmarketing",
                "salaire": Decimal("1441.62"), "cadre": False, "classification": "",
                "pas": Decimal("0"), "type": "alternance", "fin": date.today() + timedelta(days=300),
            },
        ]
        for data in employes_data:
            employee, _ = Employee.objects.get_or_create(
                company=company, matricule=data["matricule"],
                defaults={
                    "first_name": data["first"],
                    "last_name": data["last"],
                    "position": data["poste"],
                    "department": "Production",
                    "hire_date": date(2023, 1, 2),
                    "status": "actif",
                    "email_pro": f"{data['first'].lower()}.{data['last'].lower()}@primevision.example",
                    "email_perso": f"{data['first'].lower()}@perso.example",
                    "phone": "+33 6 00 00 00 00",
                    "address": "3 rue des Lilas, 75020 Paris",
                    "social_security_number": "2901234567890" + data["matricule"][-1],
                    "bank_iban": "FR7630004000031234567890143",
                    "bank_bic": "BNPAFRPPXXX",
                    "user": data.get("user"),
                },
            )
            Contract.objects.get_or_create(
                employee=employee,
                start_date=date(2023, 1, 2),
                defaults={
                    "contract_type": data.get("type", "cdi"),
                    "end_date": data.get("fin"),
                    "weekly_hours": Decimal("35"),
                    "gross_monthly_salary": data["salaire"],
                    "is_cadre": data["cadre"],
                    "classification": data.get("classification", ""),
                    "withholding_rate": data.get("pas", 0),
                },
            )
            for lt in (cp, rtt):
                LeaveBalance.objects.get_or_create(
                    company=company, employee=employee, leave_type=lt, year=date.today().year,
                    defaults={"acquired": lt.annual_days, "taken": 0},
                )

        # --- Paie : jeu de règles de référence (provisoire) --------------------
        from apps.payroll.models import PayrollParameterSet

        if not PayrollParameterSet.objects.filter(company=company).exists():
            creer_ruleset_reference(company, admin)
            self.stdout.write(self.style.WARNING(
                "Jeu de règles de paie 2025 créé en statut PROVISOIRE — à faire vérifier."
            ))

        # --- Facturation -------------------------------------------------------
        clients_data = [
            ("ACME", "ACME Industrie", "contact@acme.example", 30),
            ("GSERV", "Globex Services", "compta@globex.example", 45),
            ("INITECH", "Initech SAS", "facturation@initech.example", 30),
        ]
        clients = {}
        for code, name, email, terms in clients_data:
            clients[code], _ = Client.objects.get_or_create(
                company=company, code=code,
                defaults={"name": name, "email": email, "payment_terms_days": terms,
                          "address": "1 rue du Client, 75010 Paris"},
            )
        for code, name in (("AWSFR", "AWS France"), ("INKA", "Imprimerie Kappa"), ("GDF", "Énergies GDF")):
            Supplier.objects.get_or_create(
                company=company, code=code,
                defaults={"name": name, "default_expense_account": "606300"},
            )

        abonnements_data = [
            (clients["ACME"], "Maintenance logicielle — offre Pro", Decimal("890"), "mensuel"),
            (clients["GSERV"], "Supervision média — offre Business", Decimal("2450"), "trimestriel"),
        ]
        for client, label, prix, periodicite in abonnements_data:
            Subscription.objects.get_or_create(
                company=company, client=client, label=label,
                defaults={
                    "periodicity": periodicite,
                    "price_ht": prix,
                    "vat_rate": Decimal("20"),
                    "start_date": date.today().replace(day=1) - timedelta(days=400),
                    "next_billing_date": date.today().replace(day=1),
                    "auto_renew": True,
                },
            )

        # --- Dépenses -----------------------------------------------------------
        categories = [
            ("REPAS", "Repas d'affaires", Decimal("25"), "625700"),
            ("DEPL", "Déplacement / transport", Decimal("0"), "625100"),
            ("HEB", "Hébergement", Decimal("120"), "625100"),
            ("FOUR", "Fournitures", Decimal("50"), "606300"),
        ]
        for code, label, plafond, compte in categories:
            ExpenseCategory.objects.get_or_create(
                company=company, code=code,
                defaults={"label": label, "max_amount": plafond, "expense_account": compte},
            )

        # --- Trésorerie ----------------------------------------------------------
        BankAccount.objects.get_or_create(
            company=company, label="Compte courant principal",
            defaults={
                "bank_name": "Banque de démonstration",
                "iban": "FR7612345678901234567890123",
                "bic": "AGRIFRPPXXX",
                "is_main": True,
                "initial_balance": Decimal("42000"),
                "initial_balance_date": date.today() - timedelta(days=180),
            },
        )

        # --- Associés ------------------------------------------------------------
        for prenom, nom, parts in (("David", "Dirigeant", 700), ("Inesse", "Investisseuse", 300)):
            Associate.objects.get_or_create(
                company=company, last_name=nom, first_name=prenom,
                defaults={"shares": parts, "entry_date": date(2021, 3, 15)},
            )

        # --- Conformité ------------------------------------------------------------
        initialiser_catalogue()
        generer_instances(company)

        # --- Modèles de documents --------------------------------------------------
        DocumentTemplate.objects.get_or_create(
            company=company, name="Contrat de travail CDI (trame)", version=1,
            defaults={
                "template_type": TemplateType.CONTRAT_TRAVAIL,
                "content": (
                    "CONTRAT DE TRAVAIL À DURÉE INDÉTERMINÉE\n\n"
                    "Entre la société {{societe}}, SIRET {{siret}},\n"
                    "et {{civilite}} {{prenom}} {{nom}}, né(e) le {{date_naissance}}.\n\n"
                    "Poste : {{poste}}\nClassification : {{classification}}\n"
                    "Rémunération brute mensuelle : {{salaire_brut}} € pour {{heures_hebdo}} h hebdomadaires.\n"
                    "Date d'effet : {{date_debut}}\n\n"
                    "Convention collective : {{convention_collective}}.\n"
                ),
            },
        )

        # --- IA : fournisseurs préconfigurés (désactivés) ---------------------------
        AIProvider.objects.get_or_create(
            company=company, kind=ProviderKind.OLLAMA,
            defaults={
                "label": "Ollama (local)",
                "base_url": "http://ollama:11434",
                "default_model": "llama3.1:8b",
                "is_enabled": False,
                "billing_info": "Gratuit, local. Licence du modèle à vérifier (ex. licence Llama).",
            },
        )
        AIProvider.objects.get_or_create(
            company=company, kind=ProviderKind.CODECRAFT,
            defaults={
                "label": "CodeCraftAPI",
                "base_url": "https://codecraftapi.com/v1",
                "is_enabled": False,
                "billing_info": "Selon le tarif du fournisseur — facultatif.",
            },
        )

        self.stdout.write(self.style.SUCCESS(
            "Jeu de démonstration prêt.\n"
            f"  Entreprise : {company.name}\n"
            f"  Compte administrateur : admin@primevision.example\n"
            f"  Mot de passe commun : {password} (à changer immédiatement)"
        ))
