import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Alerte } from "@/components/ui/modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { Tabs } from "@/components/ui/tabs";
import { toast } from "sonner";
import { Bot, SendHorizontal } from "lucide-react";

function Assistant() {
  const [question, setQuestion] = useState("");
  const [reponse, setReponse] = useState<string | null>(null);
  const { data: status } = useQuery({
    queryKey: ["ai-status"],
    queryFn: async () => (await api.get("ai/status/")).data,
  });
  const poser = useMutation<any, unknown, void>({
    mutationFn: () => api.post("ai/assist/", { question }),
    onSuccess: (res) => setReponse(res.data?.answer ?? res.data?.response ?? JSON.stringify(res.data, null, 2)),
    onError: notifierErreur,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Bot className="h-5 w-5" /> Assistant interne
          {status && (
            <Badge variant={status.enabled ? "success" : "muted"}>
              {status.enabled ? `Actif (${status.provider})` : "Désactivé"}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Alerte variante="warning">
          L'assistant est un <strong>aide-documentaire interne</strong> : ses réponses doivent être vérifiées.
          Il ne décide jamais seul des virements, de la paie, des dividendes ni des déclarations.
          Clé API hébergée côté serveur (jamais exposée au navigateur, ni dans le code, ni dans les logs).
        </Alerte>
        {status && !status.enabled && (
          <Alerte variante="info">
            L'IA est actuellement désactivée pour votre entreprise. Activez un fournisseur dans l'onglet « Fournisseurs ».
            Le reste de l'application fonctionne intégralement sans IA.
          </Alerte>
        )}
        <div className="space-y-1">
          <Label htmlFor="question">Votre question</Label>
          <Textarea id="question" value={question} onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ex. Résume les étapes de clôture de la paie de ce mois…" />
        </div>
        <div className="flex justify-end">
          <Button onClick={() => poser.mutate()} disabled={!question || poser.isPending || (status && !status.enabled)}>
            <SendHorizontal className="h-4 w-4" /> {poser.isPending ? "Envoi…" : "Envoyer"}
          </Button>
        </div>
        {reponse && (
          <div className="rounded-md border bg-muted/40 p-3 text-sm whitespace-pre-wrap">{reponse}</div>
        )}
      </CardContent>
    </Card>
  );
}

function Fournisseurs() {
  return (
    <ResourcePage
      titre="Fournisseurs IA"
      description="Ollama local par défaut ; CodeCraftAPI (https://codecraftapi.com/v1) disponible. Les clés restent chiffrées côté serveur."
      endpoint="ai/providers/"
      colonnes={[
        { key: "name", label: "Nom" },
        { key: "provider_type", label: "Type" },
        { key: "base_url", label: "URL de base" },
        { key: "default_model", label: "Modèle" },
        {
          key: "is_enabled", label: "Statut",
          render: (p: any) => <Badge variant={p.is_enabled ? "success" : "muted"}>{p.is_enabled ? "Activé" : "Désactivé"}</Badge>,
        },
      ]}
      champs={[
        { name: "name", label: "Nom", required: true },
        { name: "provider_type", label: "Type", type: "select", required: true, options: [
          { value: "ollama", label: "Ollama (local, par défaut)" },
          { value: "codecraft", label: "CodeCraftAPI" },
        ]},
        { name: "base_url", label: "URL de base (ex. http://localhost:11434 ou https://codecraftapi.com/v1)" },
        { name: "default_model", label: "Modèle par défaut (aucun identifiant codé en dur)" },
        { name: "api_key", label: "Clé API (chiffrée côté serveur)", type: "password" },
      ]}
    />
  );
}

export default function IaPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Assistant IA</h1>
      <Tabs onglets={[
        { id: "assistant", label: "Assistant", contenu: <Assistant /> },
        { id: "fournisseurs", label: "Fournisseurs", contenu: <Fournisseurs /> },
      ]} />
    </div>
  );
}
