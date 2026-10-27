import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";

export default function EntreprisePage() {
  return (
    <ResourcePage
      titre="Mes entreprises"
      description="Sociétés auxquelles vous êtes rattaché. Les actions sensibles sont journalisées."
      endpoint="organization/companies/"
      colonnes={[
        { key: "name", label: "Raison sociale" },
        { key: "legal_form", label: "Forme" },
        { key: "siren", label: "SIREN" },
        { key: "share_capital", label: "Capital (€)" },
        {
          key: "vat_filed", label: "TVA",
          render: (c: any) => <Badge variant={c.vat_filed ? "success" : "muted"}>{c.vat_filed ? "Déclarée" : "—"}</Badge>,
        },
      ]}
      champs={[
        { name: "name", label: "Raison sociale", required: true },
        { name: "legal_form", label: "Forme juridique", type: "select", options: [
          { value: "SAS", label: "SAS" }, { value: "SARL", label: "SARL" }, { value: "SA", label: "SA" },
          { value: "EURL", label: "EURL" }, { value: "SASU", label: "SASU" }, { value: "EI", label: "EI" }, { value: "Autre", label: "Autre" },
        ]},
        { name: "share_capital", label: "Capital social (€)", type: "number", step: "0.01" },
        { name: "siren", label: "SIREN (9 chiffres)", required: true },
        { name: "siret", label: "SIRET (14 chiffres)", required: true },
        { name: "vat_number", label: "N° TVA intracommunautaire" },
        { name: "address", label: "Adresse", type: "textarea" },
        { name: "rcs_city", label: "Ville RCS" },
        { name: "ape_code", label: "Code APE/NAF" },
        { name: "activity_start_date", label: "Début d'activité", type: "date", required: true },
      ]}
    />
  );
}
