import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";

export default function ClientsPage() {
  return (
    <ResourcePage
      titre="Clients"
      description="Clients de facturation. Supprimer un client n'efface jamais ses factures émises (immuable)."
      endpoint="invoicing/clients/"
      colonnes={[
        { key: "code", label: "Code" },
        { key: "name", label: "Nom" },
        { key: "email", label: "Email" },
        { key: "siret", label: "SIRET" },
        { key: "payment_terms_days", label: "Règlement (j)" },
        {
          key: "is_active", label: "Statut",
          render: (c: any) => <Badge variant={c.is_active ? "success" : "muted"}>{c.is_active ? "Actif" : "Inactif"}</Badge>,
        },
      ]}
      champs={[
        { name: "code", label: "Code client", required: true },
        { name: "name", label: "Nom / raison sociale", required: true },
        { name: "email", label: "Email", type: "email" },
        { name: "phone", label: "Téléphone" },
        { name: "siret", label: "SIRET" },
        { name: "vat_number", label: "N° TVA intracom." },
        { name: "address", label: "Adresse de facturation", type: "textarea" },
        { name: "payment_terms_days", label: "Délai de règlement (jours)", type: "number", min: "0" },
        {
          name: "is_active", label: "Statut", type: "select",
          options: [{ value: "true", label: "Actif" }, { value: "false", label: "Inactif" }],
        },
        { name: "notes", label: "Notes", type: "textarea" },
      ]}
    />
  );
}
