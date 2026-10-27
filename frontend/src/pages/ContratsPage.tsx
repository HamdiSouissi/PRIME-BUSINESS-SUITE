import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Tabs } from "@/components/ui/tabs";
import { Alerte } from "@/components/ui/modal";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

function Modeles() {
  return (
    <ResourcePage
      titre="Modèles de documents"
      description="Modèles DOCX avec variables {entreprise.nom}, {salarie.prenom}, etc. — téléchargeables, jamais « signés électroniquement de manière qualifiée »."
      endpoint="contracts/templates/"
      colonnes={[
        { key: "name", label: "Nom" },
        { key: "type_label", label: "Type" },
        {
          key: "status", label: "Statut",
          render: (t: any) => <Badge variant={t.status === "valide" ? "success" : t.status === "archive" ? "muted" : "warning"}>{t.status_label ?? t.status}</Badge>,
        },
      ]}
      champs={[
        { name: "name", label: "Nom du modèle", required: true },
        { name: "template_type", label: "Type de modèle", type: "select", options: [
          { value: "contrat_travail", label: "Contrat de travail" },
          { value: "avenant", label: "Avenant" },
          { value: "embauche", label: "Document d'embauche" },
          { value: "fin_contrat", label: "Document de fin de contrat" },
          { value: "prestation", label: "Contrat de prestation" },
          { value: "maintenance", label: "Contrat de maintenance" },
          { value: "abonnement", label: "Contrat d'abonnement" },
          { value: "cgv", label: "Conditions commerciales" },
          { value: "pv", label: "Procès-verbal / décision sociale" },
          { value: "autre", label: "Autre" },
        ], required: true },
        { name: "content", label: "Contenu (variables entre accolades)", type: "textarea", required: true },
        { name: "legal_review_note", label: "Note de revue juridique", type: "textarea" },
      ]}
    />
  );
}

function Documents() {
  const { data } = useQuery({
    queryKey: ["contracts/documents/"],
    queryFn: async () => {
      const res = await api.get("contracts/documents/");
      const d = res.data;
      return Array.isArray(d) ? d : d.results ?? [];
    },
  });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Documents générés</CardTitle></CardHeader>
      <CardContent className="space-y-2">
        {(data ?? []).map((docu: any) => (
          <div key={docu.id} className="flex items-center justify-between rounded border p-2 text-sm">
            <div>
              <p className="font-medium">{docu.label}</p>
              <p className="text-xs text-muted-foreground">Modèle {docu.template_name} — {docu.created_at ? new Date(docu.created_at).toLocaleString("fr-FR") : ""}</p>
            </div>
            <Badge variant="muted">{docu.format ?? "DOCX"}</Badge>
          </div>
        ))}
        {!(data ?? []).length && <p className="text-sm text-muted-foreground">Aucun document généré pour l'instant.</p>}
      </CardContent>
    </Card>
  );
}

export default function ContratsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Contrats & modèles de documents</h1>
      <Alerte variante="warning">
        Les documents générés sont des <strong>modèles modifiables</strong> : vérifiez chaque exemplaire avant usage.
        L'éventuelle « signature » intégrée n'est <strong>pas</strong> une signature électronique qualifiée — un flux
        de signature conforme eIDAS nécessiterait un prestataire dédié.
      </Alerte>
      <Tabs onglets={[
        { id: "documents", label: "Documents", contenu: <Documents /> },
        { id: "modeles", label: "Modèles", contenu: <Modeles /> },
      ]} />
    </div>
  );
}
