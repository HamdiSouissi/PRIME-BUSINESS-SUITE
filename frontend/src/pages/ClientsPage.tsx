import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";

export default function ClientsPage() {
  return (
    <ResourcePage
      titre="Clients"
      description="Clients de facturation. Supprimer un client n'efface jamais ses factures émises (immuable)."
      endpoint="invoicing/clients/"
      colonnes={[
        { key: "name", label: "Nom" },
        { key: "email", label: "Email" },
        { key: "siret", label: "SIRET" },
        { key: "payment_terms", label: "Règlement" },
        {
          key: "is_active", label: "Statut",
          render: (c: any) => <Badge variant={c.is_active ? "success" : "muted"}>{c.is_active ? "Actif" : "Inactif"}</Badge>,
        },
      ]}
      champs={[
        { name: "name", label: "Nom / raison sociale", required: true },
        { name: "email", label: "Email", type: "email" },
        { name: "phone", label: "Téléphone" },
        { name: "siret", label: "SIRET" },
        { name: "vat_number", label: "N° TVA intracom." },
        { name: "billing_address", label: "Adresse de facturation", type: "textarea" },
        { name: "payment_terms", label: "Délai de règlement", type: "select", options: [
          { value: "comptant", label: "Comptant" },
          { value: "30j", label: "30 jours" },
          { value: "45j", label: "45 jours" },
          { value: "60j", label: "60 jours" },
        ]},
      ]}
    />
  );
}
