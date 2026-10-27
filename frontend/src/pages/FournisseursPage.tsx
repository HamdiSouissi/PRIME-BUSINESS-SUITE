import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";

export default function FournisseursPage() {
  return (
    <ResourcePage
      titre="Fournisseurs"
      description="Fournisseurs d'achat. Séparés des clients pour éviter toute confusion d'écritures."
      endpoint="invoicing/suppliers/"
      colonnes={[
        { key: "code", label: "Code" },
        { key: "name", label: "Nom" },
        { key: "email", label: "Email" },
        { key: "siret", label: "SIRET" },
        { key: "default_expense_account", label: "Compte de charge" },
        { key: "is_active", label: "Statut", render: (s: any) => <Badge variant={s.is_active ? "success" : "muted"}>{s.is_active ? "Actif" : "Inactif"}</Badge> },
      ]}
      champs={[
        { name: "code", label: "Code fournisseur", required: true },
        { name: "name", label: "Nom / raison sociale", required: true },
        { name: "email", label: "Email", type: "email" },
        { name: "phone", label: "Téléphone" },
        { name: "address", label: "Adresse", type: "textarea" },
        { name: "siret", label: "SIRET" },
        { name: "vat_number", label: "N° TVA intracom." },
        { name: "default_expense_account", label: "Compte de charge par défaut" },
        {
          name: "is_active", label: "Statut", type: "select",
          options: [{ value: "true", label: "Actif" }, { value: "false", label: "Inactif" }],
        },
      ]}
    />
  );
}
