import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, clearTokens, storeTokens } from "./api";

export interface Utilisateur {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
}

interface Profil {
  user: Utilisateur;
  role: string | null;
  active_company: number | null;
  active_company_name: string;
  memberships: Array<{ company: number; company_name: string; role: string; role_label: string }>;
}

interface AuthContextType {
  profil: Profil | null;
  chargement: boolean;
  connexion: (email: string, motDePasse: string) => Promise<void>;
  deconnexion: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function Roles() {
  return {
    admin: "administrateur",
    direction: "direction",
    rh: "ressources_humaines",
    paie: "gestionnaire_paie",
    comptable: "comptable",
    finance: "responsable_financier",
    manager: "manager",
    salarie: "salarie",
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [profil, setProfil] = useState<Profil | null>(null);
  const [chargement, setChargement] = useState(true);

  useEffect(() => {
    api
      .get<Profil>("/auth/me/")
      .then((res) => setProfil(res.data))
      .catch(() => setProfil(null))
      .finally(() => setChargement(false));
  }, []);

  const valeur = useMemo<AuthContextType>(
    () => ({
      profil,
      chargement,
      async connexion(email, motDePasse) {
        const res = await api.post("/auth/login/", { email, password: motDePasse });
        storeTokens(res.data.access, res.data.refresh);
        const me = await api.get<Profil>("/auth/me/");
        setProfil(me.data);
      },
      deconnexion() {
        clearTokens();
        setProfil(null);
      },
    }),
    [profil, chargement]
  );

  return <AuthContext.Provider value={valeur}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être dans AuthProvider");
  return ctx;
}

export function useRole() {
  const { profil } = useAuth();
  return profil?.role ?? null;
}
