import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fmtEuro } from "@/lib/utils";
import { toast } from "sonner";
import { PlayCircle, PauseCircle, Play, XCircle } from "lucide-react";

const STATUTS: Record<string, any> = {
  actif: "success", essai: "info", suspendu: "warning", resilie: "danger",
};

export default function AbonnementsPage() {
  const qc = useQueryClient();
  const { data: indicateurs } = useQuery({
    queryKey: ["abo-indicateurs"],
    queryFn: async () => (await api.get("subscriptions/subscriptions/indicateurs/")).data,
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["subscriptions/subscriptions/"] });

  const facturer = useMutation<any, unknown, void>({
    mutationFn: () => api.post("subscriptions/subscriptions/facturer-echues/", {}),
    onSuccess: (res) => {
      const n = res.data?.generees ?? res.data?.created ?? 0;
      toast.success(`${n} facture(s) générée(s). La génération est idempotente : aucune double facturation.`);
      qc.invalidateQueries();
    },
    onError: notifierErreur,
  });

  const agir = useMutation<any, unknown, { id: number; act: string; payload?: Record<string, string> }>({
    mutationFn: ({ id, act, payload }) => api.post(`subscriptions/subscriptions/${id}/${act}/`, payload ?? {}),
    onSuccess: () => { toast.success("Abonnement mis à jour."); refresh(); },
    onError: notifierErreur,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Abonnements</h1>
          <p className="text-sm text-muted-foreground">MRR/ARR calculés sur les abonnements actifs (définitions affichées).</p>
        </div>
        <Button onClick={() => facturer.mutate()} disabled={facturer.isPending}>
          <PlayCircle className="h-4 w-4" /> Facturer les échéances
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">MRR (HT)</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-semibold">{indicateurs?.mrr_ht != null ? fmtEuro(indicateurs.mrr_ht) : "—"}</p></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">ARR (×12, HT)</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-semibold">{indicateurs?.arr_ht != null ? fmtEuro(indicateurs.arr_ht) : "—"}</p></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Actifs</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-semibold">{indicateurs?.abonnements_actifs ?? "—"}</p></CardContent></Card>
      </div>

      <ResourcePage
        titre="Abonnements"
        endpoint="subscriptions/subscriptions/"
        colonnes={[
          { key: "client_name", label: "Client" },
          { key: "label", label: "Offre" },
          { key: "periodicity", label: "Périodicité" },
          { key: "price_ht", label: "Prix HT" },
          { key: "next_billing_date", label: "Prochaine échéance" },
          { key: "status", label: "Statut", render: (s: any) => <Badge variant={STATUTS[s.status] ?? "muted"}>{s.status}</Badge> },
        ]}
        champs={[
          { name: "client", label: "Client", type: "select", optionsUrl: "invoicing/clients/", required: true },
          { name: "label", label: "Intitulé de l'offre", required: true },
          { name: "price_ht", label: "Prix HT par période", type: "number", step: "0.01", required: true },
          { name: "periodicity", label: "Périodicité", type: "select", required: true, options: [
            { value: "mensuel", label: "Mensuel" }, { value: "trimestriel", label: "Trimestriel" }, { value: "annuel", label: "Annuel" },
          ]},
          { name: "start_date", label: "Début", type: "date", required: true },
          { name: "next_billing_date", label: "Prochaine échéance de facturation", type: "date", required: true },
          { name: "end_date", label: "Fin (optionnel)", type: "date" },
        ]}
        actions={(s: any) => (
          <>
            {s.status === "actif" && (
              <Button size="icon" variant="ghost" title="Suspendre"
                onClick={() => agir.mutate({ id: s.id, act: "suspendre" })}>
                <PauseCircle className="h-4 w-4" />
              </Button>
            )}
            {s.status === "suspendu" && (
              <Button size="icon" variant="ghost" title="Réactiver"
                onClick={() => agir.mutate({ id: s.id, act: "reactiver" })}>
                <Play className="h-4 w-4" />
              </Button>
            )}
            {s.status !== "resilie" && (
              <Button size="icon" variant="ghost" title="Résilier"
                onClick={() => {
                  const raison = window.prompt("Motif de résiliation (optionnel) :") ?? "";
                  agir.mutate({ id: s.id, act: "resilier", payload: { raison } });
                }}>
                <XCircle className="h-4 w-4 text-destructive" />
              </Button>
            )}
          </>
        )}
      />
    </div>
  );
}
