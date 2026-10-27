import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";

export default function FournisseursPage() {
  return (
    <ResourcePage
      titre="Fournisseurs"
      description="Fournisseurs d'achat. Séparés des clients pour éviter toute confusion d'écritures."
      endpoint="invoicing/suppliers/"
      colonnes={[
        { key: "name", label: "Nom" },
        { key: "email", label: "Email" },
        { key: "siret", label: "SIRET" },
        { key: "category", label: "Catégorie" },
        { key: "is_active", label: "Statut", render: (s: any) => <Badge variant={s.is_active ? "success" : "muted"}>{s.is_active ? "Actif" : "Inactif"}</Badge> },
      ]}
      champs={[
        { name: "name", label: "Nom / raison sociale", required: true },
        { name: "email", label: "Email", type: "email" },
        { name: "phone", label: "Téléphone" },
        { name: "siret", label: "SIRET" },
        { name: "category", label: "Catégorie" },
        { name: "payment_terms", label: "Délai convenu" },
        { name: "iban", label: "IBAN" },
      ]}
    />
  );
}
