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
        { key: "category", label: "Catégorie" },
        {
          key: "is_active", label: "Actif",
          render: (t: any) => <Badge variant={t.is_active ? "success" : "muted"}>{t.is_active ? "Oui" : "Non"}</Badge>,
        },
      ]}
      champs={[
        { name: "name", label: "Nom du modèle", required: true },
        { name: "category", label: "Catégorie", type: "select", options: [
          { value: "contrat_travail", label: "Contrat de travail" },
          { value: "avenant", label: "Avenant" },
          { value: "attestation", label: "Attestation" },
          { value: "autre", label: "Autre" },
        ], required: true },
        { name: "description", label: "Description", type: "textarea" },
        { name: "content", label: "Contenu (variables entre accolades)", type: "textarea", required: true },
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
              <p className="font-medium">{docu.name}</p>
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
