"""Routage principal de l'API Prime Business Suite."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounting.views import AccountViewSet, FiscalYearViewSet, JournalEntryViewSet, JournalViewSet
from apps.accounts.views import LoginView, MeView, UserViewSet
from apps.ai_assistant.views import (
    AIAssistView,
    AIProviderViewSet,
    AIStatusView,
    AIUsageLogViewSet,
    FeatureRoutingViewSet,
)
from apps.budgets.views import BudgetLineViewSet, BudgetViewSet
from apps.compliance.views import ObligationDefinitionViewSet, ObligationInstanceViewSet
from apps.contracts.views import DocumentTemplateViewSet, GeneratedDocumentViewSet
from apps.core.views import AuditLogView, DashboardView, DocumentDownloadView, health
from apps.dividends.views import (
    AssociateViewSet,
    CapitalMovementViewSet,
    CurrentAccountEntryViewSet,
    DistributionDecisionViewSet,
    DividendPaymentViewSet,
)
from apps.expenses.views import ExpenseCategoryViewSet, ExpenseLineViewSet, ExpenseReportViewSet
from apps.hr.views import (
    ContractViewSet,
    EmployeeDocumentViewSet,
    EmployeeViewSet,
    EquipmentItemViewSet,
    InterviewViewSet,
    LeaveBalanceViewSet,
    LeaveRequestViewSet,
    LeaveTypeViewSet,
    TrainingRecordViewSet,
)
from apps.invoicing.views import (
    ClientViewSet,
    EInvoicingConfigViewSet,
    InvoiceViewSet,
    PaymentScheduleViewSet,
    PaymentViewSet,
    QuoteViewSet,
    SupplierInvoiceViewSet,
    SupplierViewSet,
)
from apps.organization.views import CompanyViewSet
from apps.payroll.views import (
    ContributionRuleViewSet,
    DSNExportViewSet,
    PayrollParameterSetViewSet,
    PayrollRunViewSet,
    PayslipViewSet,
)
from apps.subscriptions.views import SubscriptionInvoiceViewSet, SubscriptionViewSet
from apps.treasury.views import BankAccountViewSet, BankTransactionViewSet, CashEventViewSet

router = DefaultRouter()
# Organisation / comptes
router.register("organization/companies", CompanyViewSet, basename="company")
router.register("accounts/users", UserViewSet, basename="user")
# RH
router.register("hr/employees", EmployeeViewSet, basename="employee")
router.register("hr/contracts", ContractViewSet, basename="contract")
router.register("hr/leave-types", LeaveTypeViewSet, basename="leave-type")
router.register("hr/leave-requests", LeaveRequestViewSet, basename="leave-request")
router.register("hr/leave-balances", LeaveBalanceViewSet, basename="leave-balance")
router.register("hr/equipment", EquipmentItemViewSet, basename="equipment")
router.register("hr/trainings", TrainingRecordViewSet, basename="training")
router.register("hr/interviews", InterviewViewSet, basename="interview")
router.register("hr/employee-documents", EmployeeDocumentViewSet, basename="employee-document")
# Paie
router.register("payroll/parameter-sets", PayrollParameterSetViewSet, basename="payroll-params")
router.register("payroll/rules", ContributionRuleViewSet, basename="payroll-rule")
router.register("payroll/runs", PayrollRunViewSet, basename="payroll-run")
router.register("payroll/payslips", PayslipViewSet, basename="payslip")
router.register("payroll/dsn", DSNExportViewSet, basename="dsn")
# Facturation
router.register("invoicing/clients", ClientViewSet, basename="client")
router.register("invoicing/suppliers", SupplierViewSet, basename="supplier")
router.register("invoicing/quotes", QuoteViewSet, basename="quote")
router.register("invoicing/invoices", InvoiceViewSet, basename="invoice")
router.register("invoicing/supplier-invoices", SupplierInvoiceViewSet, basename="supplier-invoice")
router.register("invoicing/payments", PaymentViewSet, basename="payment")
router.register("invoicing/schedules", PaymentScheduleViewSet, basename="schedule")
router.register("invoicing/einvoicing", EInvoicingConfigViewSet, basename="einvoicing")
# Abonnements
router.register("subscriptions/subscriptions", SubscriptionViewSet, basename="subscription")
router.register("subscriptions/generated", SubscriptionInvoiceViewSet, basename="subscription-invoice")
# Dépenses
router.register("expenses/categories", ExpenseCategoryViewSet, basename="expense-category")
router.register("expenses/reports", ExpenseReportViewSet, basename="expense-report")
router.register("expenses/lignes", ExpenseLineViewSet, basename="expense-line")
# Comptabilité
router.register("accounting/accounts", AccountViewSet, basename="account")
router.register("accounting/journals", JournalViewSet, basename="journal")
router.register("accounting/fiscal-years", FiscalYearViewSet, basename="fiscal-year")
router.register("accounting/entries", JournalEntryViewSet, basename="entry")
# Trésorerie
router.register("treasury/bank-accounts", BankAccountViewSet, basename="bank-account")
router.register("treasury/transactions", BankTransactionViewSet, basename="bank-transaction")
router.register("treasury/cash-events", CashEventViewSet, basename="cash-event")
# Budgets
router.register("budgets/budgets", BudgetViewSet, basename="budget")
router.register("budgets/lines", BudgetLineViewSet, basename="budget-line")
# Associés / dividendes
router.register("dividends/associates", AssociateViewSet, basename="associate")
router.register("dividends/capital-movements", CapitalMovementViewSet, basename="capital-movement")
router.register("dividends/current-accounts", CurrentAccountEntryViewSet, basename="current-account")
router.register("dividends/distributions", DistributionDecisionViewSet, basename="distribution")
router.register("dividends/paiements", DividendPaymentViewSet, basename="dividend-payment")
# Conformité
router.register("compliance/definitions", ObligationDefinitionViewSet, basename="obligation-definition")
router.register("compliance/instances", ObligationInstanceViewSet, basename="obligation-instance")
# Contrats / documents
router.register("contracts/templates", DocumentTemplateViewSet, basename="template")
router.register("contracts/documents", GeneratedDocumentViewSet, basename="document")
# IA
router.register("ai/providers", AIProviderViewSet, basename="ai-provider")
router.register("ai/routings", FeatureRoutingViewSet, basename="ai-routing")
router.register("ai/usage", AIUsageLogViewSet, basename="ai-usage")

urlpatterns = [
    path("api/health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    # Auth
    path("api/auth/login/", LoginView.as_view(), name="login"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("api/auth/me/", MeView.as_view(), name="me"),
    # Transversal
    path("api/dashboard/", DashboardView.as_view(), name="dashboard"),
    path("api/audit/", AuditLogView.as_view(), name="audit"),
    path("api/documents/hr/<int:pk>/telecharger/", DocumentDownloadView.as_view(), name="doc-hr"),
    # IA
    path("api/ai/status/", AIStatusView.as_view(), name="ai-status"),
    path("api/ai/assist/", AIAssistView.as_view(), name="ai-assist"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
