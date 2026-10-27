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
          key: "vat_regime", label: "Régime TVA",
          render: (c: any) => <Badge variant="default">{c.vat_regime}</Badge>,
        },
      ]}
      champs={[
        { name: "name", label: "Raison sociale", required: true },
        { name: "legal_form", label: "Forme juridique", type: "select", required: true, options: [
          { value: "sas", label: "SAS" }, { value: "sasu", label: "SASU" },
          { value: "sarl", label: "SARL" }, { value: "eurl", label: "EURL" },
          { value: "sa", label: "SA" }, { value: "snc", label: "SNC" },
          { value: "sci", label: "SCI" }, { value: "ei", label: "Entreprise individuelle" },
          { value: "autre", label: "Autre" },
        ]},
        { name: "share_capital", label: "Capital social (€)", type: "number", step: "0.01" },
        { name: "siren", label: "SIREN (9 chiffres)" },
        { name: "siret", label: "SIRET (14 chiffres)" },
        { name: "vat_number", label: "N° TVA intracommunautaire" },
        {
          name: "vat_regime", label: "Régime de TVA", type: "select", options: [
            { value: "reel_normal", label: "Réel normal" },
            { value: "reel_simplifie", label: "Réel simplifié" },
            { value: "franchise", label: "Franchise en base de TVA" },
            { value: "non_assujetti", label: "Non assujetti" },
          ],
        },
        { name: "address", label: "Adresse", type: "textarea" },
        { name: "postal_code", label: "Code postal" },
        { name: "city", label: "Ville" },
        { name: "rcs_city", label: "Ville RCS" },
        { name: "naf_code", label: "Code APE/NAF" },
        { name: "email", label: "E-mail", type: "email" },
        { name: "phone", label: "Téléphone" },
        { name: "website", label: "Site web" },
      ]}
    />
  );
}
