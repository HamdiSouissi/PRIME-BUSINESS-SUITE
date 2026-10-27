import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Tabs } from "@/components/ui/tabs";
import { Alerte } from "@/components/ui/modal";

// Statuts d'un salarié (apps.hr.models.Employee.STATUTS)
const STATUTS = [
  { value: "actif", label: "Actif" },
  { value: "conge", label: "En congé" },
  { value: "inactif", label: "Inactif" },
];

// Types de contrat (apps.hr.models.Contract.TYPES) — valeurs en minuscules
const TYPES_CONTRAT = [
  { value: "cdi", label: "CDI" },
  { value: "cdd", label: "CDD" },
  { value: "alternance", label: "Alternance / apprentissage" },
  { value: "stage", label: "Stage" },
  { value: "freelance", label: "Prestation indépendante" },
  { value: "autre", label: "Autre" },
];

function Salaries() {
  return (
    <ResourcePage
      titre="Salariés"
      description="Identités personnelle et professionnelle sont séparées. Les données sensibles (santé, syndical, infractions) relèvent d'habilitation renforcée."
      endpoint="hr/employees/"
      colonnes={[
        { key: "matricule", label: "Matricule" },
        { key: "full_name", label: "Nom" },
        { key: "email_pro", label: "Email pro" },
        { key: "phone", label: "Tél." },
        { key: "hire_date", label: "Entrée" },
        {
          key: "status", label: "Statut",
          render: (e: any) => (
            <Badge variant={e.status === "actif" ? "success" : "muted"}>
              {e.status_label ?? e.status}
            </Badge>
          ),
        },
      ]}
      champs={[
        { name: "matricule", label: "Matricule", required: true },
        { name: "first_name", label: "Prénom", required: true },
        { name: "last_name", label: "Nom", required: true },
        { name: "email_perso", label: "Email personnel", type: "email" },
        { name: "email_pro", label: "Email professionnel", type: "email" },
        { name: "phone", label: "Téléphone" },
        { name: "birth_date", label: "Date de naissance", type: "date" },
        { name: "hire_date", label: "Date d'embauche", type: "date", required: true },
        { name: "position", label: "Poste" },
        // « department » est un champ libre du modèle (pas de table dédiée) :
        // saisie texte, pas d'endpoint organization/departments (inexistant).
        { name: "department", label: "Service" },
        { name: "status", label: "Statut", type: "select", options: STATUTS },
        { name: "social_security_number", label: "N° de sécurité sociale" },
        { name: "bank_iban", label: "IBAN" },
        { name: "manager", label: "Manager", type: "select", optionsUrl: "hr/employees/" },
      ]}
    />
  );
}

function Contrats() {
  return (
    <ResourcePage
      titre="Contrats de travail"
      description="CDI/CDD et avenants. Les éléments contractuels clés sont enregistrés pour alimenter la paie."
      endpoint="hr/contracts/"
      colonnes={[
        { key: "employee_name", label: "Salarié" },
        { key: "type_label", label: "Type" },
        { key: "start_date", label: "Début" },
        { key: "end_date", label: "Fin (CDD)" },
        { key: "gross_monthly_salary", label: "Salaire brut (€)" },
      ]}
      champs={[
        { name: "employee", label: "Salarié", type: "select", optionsUrl: "hr/employees/", required: true },
        { name: "contract_type", label: "Type", type: "select", required: true, options: TYPES_CONTRAT },
        { name: "start_date", label: "Début", type: "date", required: true },
        { name: "end_date", label: "Fin (obligatoire CDD/alternance/stage)", type: "date" },
        { name: "gross_monthly_salary", label: "Salaire brut mensuel (€)", type: "number", step: "0.01", required: true },
        { name: "weekly_hours", label: "Volume horaire hebdo", type: "number", step: "0.5" },
        {
          name: "is_cadre", label: "Statut cadre", type: "select",
          options: [{ value: "false", label: "Non" }, { value: "true", label: "Oui" }],
        },
        { name: "withholding_rate", label: "Taux de prélèvement à la source (%)", type: "number", step: "0.01" },
      ]}
    />
  );
}

export default function EmployesPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Ressources humaines</h1>
      <Alerte variante="info">
        Données personnelles : elles servent à la gestion RH et à la paie selon les finalités déclarées dans votre registre. Export/suppression sur demande portée par le salarié (droit d'accès pour lui-même uniquement).
      </Alerte>
      <Tabs onglets={[
        { id: "salaries", label: "Salariés", contenu: <Salaries /> },
        { id: "contrats", label: "Contrats", contenu: <Contrats /> },
      ]} />
    </div>
  );
}
