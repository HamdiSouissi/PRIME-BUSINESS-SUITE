import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { toast } from "sonner";
import { ShieldCheck } from "lucide-react";
import { useState } from "react";

const ROLES = [
  { value: "administrateur", label: "Administrateur" },
  { value: "direction", label: "Direction" },
  { value: "ressources_humaines", label: "Ressources humaines" },
  { value: "gestionnaire_paie", label: "Gestionnaire de paie" },
  { value: "comptable", label: "Comptable" },
  { value: "responsable_financier", label: "Responsable financier" },
  { value: "manager", label: "Manager" },
  { value: "salarie", label: "Salarié (portail)" },
];

export default function UtilisateursPage() {
  const qc = useQueryClient();
  const [cible, setCible] = useState<any>(null);
  const [role, setRole] = useState("salarie");

  const changerRole = useMutation<any, unknown, void>({
    mutationFn: () => api.post(`accounts/users/${cible.id}/role/`, { role }),
    onSuccess: () => {
      toast.success("Rôle mis à jour — journal d'audit alimenté.");
      setCible(null);
      qc.invalidateQueries({ queryKey: ["accounts/users/"] });
    },
    onError: notifierErreur,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Utilisateurs & rôles</h1>
      <p className="text-sm text-muted-foreground">
        RBAC — 8 rôles par défaut. Chaque changement de rôle est journalisé. Les salariés n'ont accès qu'à leur portail.
      </p>
      <ResourcePage
        titre="Comptes utilisateurs"
        endpoint="accounts/users/"
        colonnes={[
          { key: "email", label: "Email" },
          { key: "first_name", label: "Prénom" },
          { key: "last_name", label: "Nom" },
          {
            key: "memberships", label: "Rôle",
            render: (u: any) => {
              const role = u.memberships?.[0]?.role;
              return <Badge>{ROLES.find((r) => r.value === role)?.label ?? role ?? "—"}</Badge>;
            },
          },
          {
            key: "is_active", label: "Actif",
            render: (u: any) => <Badge variant={u.is_active ? "success" : "muted"}>{u.is_active ? "Oui" : "Non"}</Badge>,
          },
        ]}
        champs={[
          { name: "email", label: "Email (identifiant de connexion)", type: "email", required: true },
          { name: "username", label: "Nom d'utilisateur (déduit de l'email si vide)", hideOnEdit: true },
          { name: "first_name", label: "Prénom", required: true },
          { name: "last_name", label: "Nom", required: true },
          { name: "phone", label: "Téléphone" },
          { name: "password", label: "Mot de passe initial", type: "password", hideOnEdit: true, required: true },
          { name: "role", label: "Rôle", type: "select", options: ROLES, required: true },
        ]}
        actions={(u: any) => (
          <Button size="icon" variant="ghost" title="Changer le rôle"
            onClick={() => { setCible(u); setRole(u.memberships?.[0]?.role ?? "salarie"); }}>
            <ShieldCheck className="h-4 w-4" />
          </Button>
        )}
      />
      <Modal ouvert={Boolean(cible)} titre={`Rôle de ${cible?.email ?? ""}`} onFermer={() => setCible(null)}>
        <div className="space-y-3">
          <Select value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </Select>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setCible(null)}>Annuler</Button>
            <Button onClick={() => changerRole.mutate()} disabled={changerRole.isPending}>Enregistrer</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
