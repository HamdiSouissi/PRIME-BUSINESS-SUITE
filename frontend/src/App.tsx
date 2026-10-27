import { Route, Routes, Navigate } from "react-router-dom";
import Layout from "@/components/layout";
import { useAuth } from "@/lib/auth";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import EntreprisePage from "@/pages/EntreprisePage";
import EmployesPage from "@/pages/EmployesPage";
import AbsencesPage from "@/pages/AbsencesPage";
import PaiePage from "@/pages/PaiePage";
import DepensesPage from "@/pages/DepensesPage";
import ClientsPage from "@/pages/ClientsPage";
import DevisPage from "@/pages/DevisPage";
import FacturesPage from "@/pages/FacturesPage";
import FournisseursPage from "@/pages/FournisseursPage";
import FacturesFournisseursPage from "@/pages/FacturesFournisseursPage";
import AbonnementsPage from "@/pages/AbonnementsPage";
import ComptabilitePage from "@/pages/ComptabilitePage";
import TresoreriePage from "@/pages/TresoreriePage";
import BudgetsPage from "@/pages/BudgetsPage";
import AssociesPage from "@/pages/AssociesPage";
import ConformitePage from "@/pages/ConformitePage";
import ContratsPage from "@/pages/ContratsPage";
import IaPage from "@/pages/IaPage";
import PortailPage from "@/pages/PortailPage";
import UtilisateursPage from "@/pages/UtilisateursPage";
import AuditPage from "@/pages/AuditPage";

function Privee() {
  const { profil, chargement } = useAuth();
  if (chargement) return <div className="flex min-h-screen items-center justify-center text-muted-foreground">Chargement…</div>;
  if (!profil) return <Navigate to="/connexion" replace />;
  return <Layout />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/connexion" element={<LoginPage />} />
      <Route element={<Privee />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/entreprise" element={<EntreprisePage />} />
        <Route path="/rh" element={<EmployesPage />} />
        <Route path="/absences" element={<AbsencesPage />} />
        <Route path="/paie" element={<PaiePage />} />
        <Route path="/depenses" element={<DepensesPage />} />
        <Route path="/clients" element={<ClientsPage />} />
        <Route path="/devis" element={<DevisPage />} />
        <Route path="/factures" element={<FacturesPage />} />
        <Route path="/fournisseurs" element={<FournisseursPage />} />
        <Route path="/factures-fournisseurs" element={<FacturesFournisseursPage />} />
        <Route path="/abonnements" element={<AbonnementsPage />} />
        <Route path="/comptabilite" element={<ComptabilitePage />} />
        <Route path="/tresorerie" element={<TresoreriePage />} />
        <Route path="/budgets" element={<BudgetsPage />} />
        <Route path="/associes" element={<AssociesPage />} />
        <Route path="/conformite" element={<ConformitePage />} />
        <Route path="/contrats" element={<ContratsPage />} />
        <Route path="/ia" element={<IaPage />} />
        <Route path="/portail" element={<PortailPage />} />
        <Route path="/utilisateurs" element={<UtilisateursPage />} />
        <Route path="/audit" element={<AuditPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
