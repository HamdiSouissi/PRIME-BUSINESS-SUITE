import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alerte } from "@/components/ui/modal";
import { Tabs } from "@/components/ui/tabs";
import { toast } from "sonner";
import { CheckCircle2, Ban } from "lucide-react";

const GRAV: Record<string, any> = { critique: "danger", haute: "warning", normale: "muted" };

function Definitions() {
  return (
    <ResourcePage
      titre="Définitions d'obligations"
      description="C'est VOUS qui définissez les échéances de votre structure — le logiciel ne prétend pas connaître votre calendrier légal."
      endpoint="compliance/definitions/"
      colonnes={[
        { key: "title", label: "Obligation" },
        { key: "category", label: "Domaine" },
        { key: "frequency", label: "Fréquence" },
        { key: "role_responsable", label: "Rôle responsable" },
      ]}
      champs={[
        { name: "title", label: "Intitulé", required: true },
        { name: "category", label: "Domaine", required: true },
        { name: "frequency", label: "Fréquence", type: "select", required: true, options: [
          { value: "mensuelle", label: "Mensuelle" }, { value: "trimestrielle", label: "Trimestrielle" },
          { value: "annuelle", label: "Annuelle" }, { value: "ponctuelle", label: "Ponctuelle" },
        ]},
        { name: "description", label: "Description", type: "textarea" },
        { name: "role_responsable", label: "Rôle responsable" },
      ]}
    />
  );
}

function Instances() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["compliance/instances/"] });
  const agir = useMutation<any, unknown, { id: number; act: "marquer-faite" | "marquer-non-applicable" }>({
    mutationFn: ({ id, act }: { id: number; act: "marquer-faite" | "marquer-non-applicable" }) =>
      api.post(`compliance/instances/${id}/${act}/`, {}),
    onSuccess: () => { toast.success("Mise à jour enregistrée — preuve archivée côté journal."); refresh(); },
    onError: notifierErreur,
  });
  return (
    <ResourcePage
      titre="Échéances"
      endpoint="compliance/instances/"
      colonnes={[
        { key: "definition_title", label: "Obligation" },
        { key: "due_date", label: "Échéance" },
        { key: "status", label: "Statut", render: (i: any) => (
          <Badge variant={i.status === "faite" ? "success" : i.status === "depassee" ? "danger" : "warning"}>{i.status}</Badge>
        )},
        { key: "severity", label: "Importance", render: (i: any) => <Badge variant={GRAV[i.severity] ?? "muted"}>{i.severity}</Badge> },
      ]}
      champs={[
        { name: "definition", label: "Définition", type: "select", optionsUrl: "compliance/definitions/", required: true },
        { name: "due_date", label: "Échéance", type: "date", required: true },
      ]}
      actions={(i: any) => ["a_faire", "depassee"].includes(i.status) ? (
        <>
          <Button size="icon" variant="ghost" title="Marquer faite" onClick={() => agir.mutate({ id: i.id, act: "marquer-faite" })}>
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          </Button>
          <Button size="icon" variant="ghost" title="Non applicable ce mois"
            onClick={() => agir.mutate({ id: i.id, act: "marquer-non-applicable" })}>
            <Ban className="h-4 w-4" />
          </Button>
        </>
      ) : null}
    />
  );
}

export default function ConformitePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Centre de conformité</h1>
      <Alerte variante="info">
        Ce module est un outil d'aide au suivi : les définitions et échéances sont saisies par vos équipes.
        Rien n'est « universellement conforme » : consultez vos conseils juridiques et comptables pour vos
        obligations spécifiques. Le registre DPO et les durées de conservation sont documentés dans la documentation.
      </Alerte>
      <Tabs onglets={[
        { id: "echeances", label: "Échéances", contenu: <Instances /> },
        { id: "definitions", label: "Définitions", contenu: <Definitions /> },
      ]} />
    </div>
  );
}
