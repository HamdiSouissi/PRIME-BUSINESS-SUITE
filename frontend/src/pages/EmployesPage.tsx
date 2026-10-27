import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Tabs } from "@/components/ui/tabs";
import { Alerte } from "@/components/ui/modal";

function Salaries() {
  return (
    <ResourcePage
      titre="Salariés"
      description="Identités personnelle et professionnelle sont séparées. Les données sensibles (santé, syndical, infractions) relèvent d'habilitation renforcée."
      endpoint="hr/employees/"
      colonnes={[
        { key: "full_name", label: "Nom" },
        { key: "pro_email", label: "Email pro" },
        { key: "pro_phone", label: "Tél. pro" },
        { key: "hire_date", label: "Entrée" },
        {
          key: "is_active", label: "Statut",
          render: (e: any) => <Badge variant={e.is_active ? "success" : "muted"}>{e.is_active ? "Actif" : "Inactif"}</Badge>,
        },
      ]}
      champs={[
        { name: "first_name", label: "Prénom", required: true },
        { name: "last_name", label: "Nom", required: true },
        { name: "personal_email", label: "Email personnel", type: "email" },
        { name: "pro_email", label: "Email professionnel", type: "email", required: true },
        { name: "personal_phone", label: "Tél. personnel" },
        { name: "pro_phone", label: "Tél. professionnel" },
        { name: "birth_date", label: "Date de naissance", type: "date" },
        { name: "hire_date", label: "Date d'embauche", type: "date", required: true },
        { name: "manager", label: "Manager", type: "select", optionsUrl: "hr/employees/" },
        { name: "department", label: "Service", type: "select", optionsUrl: "organization/departments/" },
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
        { key: "contract_type", label: "Type" },
        { key: "start_date", label: "Début" },
        { key: "end_date", label: "Fin (CDD)" },
        { key: "base_salary", label: "Salaire brut (€)" },
      ]}
      champs={[
        { name: "employee", label: "Salarié", type: "select", optionsUrl: "hr/employees/", required: true },
        { name: "contract_type", label: "Type", type: "select", required: true, options: [
          { value: "CDI", label: "CDI" }, { value: "CDD", label: "CDD" },
          { value: "AVENANT", label: "Avenant" }, { value: "AUTRE", label: "Autre" },
        ]},
        { name: "start_date", label: "Début", type: "date", required: true },
        { name: "end_date", label: "Fin (CDD)", type: "date" },
        { name: "base_salary", label: "Salaire brut mensuel (€)", type: "number", step: "0.01", required: true },
        { name: "weekly_hours", label: "Volume horaire hebdo", type: "number", step: "0.5" },
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
