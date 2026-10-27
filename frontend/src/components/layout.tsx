import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Building2, Users, Banknote, FileText, Landmark, Receipt, RefreshCcw, Wallet,
  PieChart, ShieldCheck, FileSignature, Sparkles, LayoutDashboard, LogOut,
  ScrollText, Calculator, UserCircle2, CalendarDays, Briefcase, LockKeyhole,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface Lien {
  to: string;
  label: string;
  icon: any;
  roles?: string[];
}

const GESTION: Lien[][] = [
  [
    { to: "/", label: "Tableau de bord", icon: LayoutDashboard },
    {
      to: "/entreprise", label: "Entreprise", icon: Building2,
      roles: ["administrateur", "direction", "comptable", "responsable_financier"],
    },
  ],
  [
    { to: "/rh", label: "Salariés", icon: Users, roles: ["administrateur", "direction", "ressources_humaines", "gestionnaire_paie", "manager"] },
    { to: "/absences", label: "Congés & absences", icon: CalendarDays, roles: ["administrateur", "direction", "ressources_humaines", "manager"] },
    { to: "/paie", label: "Paie", icon: Banknote, roles: ["administrateur", "gestionnaire_paie", "direction", "responsable_financier"] },
    { to: "/depenses", label: "Notes de frais", icon: Wallet },
  ],
  [
    { to: "/clients", label: "Clients", icon: UserCircle2 },
    { to: "/devis", label: "Devis", icon: FileText },
    { to: "/factures", label: "Factures clients", icon: Receipt },
    {
      to: "/fournisseurs", label: "Fournisseurs", icon: Briefcase,
      roles: ["administrateur", "direction", "responsable_financier", "comptable"],
    },
    {
      to: "/factures-fournisseurs", label: "Factures fournisseurs", icon: Receipt,
      roles: ["administrateur", "direction", "responsable_financier", "comptable"],
    },
    { to: "/abonnements", label: "Abonnements (MRR)", icon: RefreshCcw },
  ],
  [
    {
      to: "/comptabilite", label: "Comptabilité", icon: Calculator,
      roles: ["administrateur", "comptable", "responsable_financier", "direction"],
    },
    {
      to: "/tresorerie", label: "Trésorerie", icon: Landmark,
      roles: ["administrateur", "responsable_financier", "comptable", "direction"],
    },
    {
      to: "/budgets", label: "Budgets & pilotage", icon: PieChart,
      roles: ["administrateur", "direction", "responsable_financier"],
    },
    {
      to: "/associes", label: "Associés & dividendes", icon: Users,
      roles: ["administrateur", "direction", "responsable_financier"],
    },
  ],
  [
    { to: "/conformite", label: "Conformité", icon: ShieldCheck, roles: ["administrateur", "direction", "ressources_humaines", "gestionnaire_paie", "comptable", "responsable_financier"] },
    { to: "/contrats", label: "Contrats & modèles", icon: FileSignature },
    { to: "/ia", label: "Assistant IA", icon: Sparkles },
  ],
  [
    { to: "/portail", label: "Mon portail", icon: UserCircle2 },
    {
      to: "/utilisateurs", label: "Utilisateurs", icon: LockKeyhole,
      roles: ["administrateur", "direction", "ressources_humaines"],
    },
    { to: "/audit", label: "Journal d'audit", icon: ScrollText, roles: ["administrateur", "direction"] },
  ],
];

const TITRES = ["Pilotage", "Humain", "Ventes", "Finances", "Configuration"];

function Groupe({ titre, liens, role }: { titre: string; liens: Lien[]; role: string | null }) {
  const visibles = liens.filter((l) => !l.roles || (role && l.roles.includes(role)));
  if (!visibles.length) return null;
  return (
    <div>
      <p className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{titre}</p>
      {visibles.map((l) => (
        <NavLink
          key={l.to}
          to={l.to}
          end={l.to === "/"}
          className={({ isActive }) =>
            cn(
              "mb-0.5 flex items-center gap-2.5 rounded-md px-3 py-1.5 text-sm transition-colors",
              isActive ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground"
            )
          }
        >
          <l.icon className="h-4 w-4 shrink-0" />
          {l.label}
        </NavLink>
      ))}
    </div>
  );
}

export default function Layout() {
  const { profil, deconnexion } = useAuth();
  const navigate = useNavigate();
  const role = profil?.role ?? null;

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 shrink-0 flex-col border-r bg-card">
        <div className="flex items-center gap-2 border-b px-4 py-3">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-primary font-bold text-primary-foreground">
            P
          </div>
          <div>
            <p className="text-sm font-semibold">Prime Business Suite</p>
            <p className="text-xs text-muted-foreground">{profil?.active_company_name || ""}</p>
          </div>
        </div>
        <nav className="flex-1 space-y-3 overflow-y-auto p-2">
          {GESTION.map((liens, i) => (
            <Groupe key={TITRES[i]} titre={TITRES[i]} liens={liens} role={role} />
          ))}
        </nav>
        <div className="border-t p-3">
          <p className="truncate text-sm font-medium">
            {profil?.user.first_name} {profil?.user.last_name}
          </p>
          <p className="truncate text-xs text-muted-foreground">{profil?.user.email}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {profil?.memberships.find((m) => m.company === profil.active_company)?.role_label ?? ""}
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="mt-1 w-full justify-start text-muted-foreground"
            onClick={() => {
              deconnexion();
              navigate("/connexion");
            }}
          >
            <LogOut className="h-4 w-4" /> Se déconnecter
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-7xl p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
