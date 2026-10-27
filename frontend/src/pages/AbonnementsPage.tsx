import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fmtEuro } from "@/lib/utils";
import { toast } from "sonner";
import { PlayCircle } from "lucide-react";

const STATUTS: Record<string, any> = {
  actif: "success", suspendu: "warning", resilie: "danger", en_essai: "info",
};

export default function AbonnementsPage() {
  const qc = useQueryClient();
  const { data: indicateurs } = useQuery({
    queryKey: ["abo-indicateurs"],
    queryFn: async () => (await api.get("subscriptions/subscriptions/indicateurs/")).data,
  });

  const facturer = useMutation<any, unknown, void>({
    mutationFn: () => api.post("subscriptions/subscriptions/facturer-echues/", {}),
    onSuccess: (res) => {
      const n = res.data?.generees ?? res.data?.created ?? 0;
      toast.success(`${n} facture(s) générée(s). La génération est idempotente : aucune double facturation.`);
      qc.invalidateQueries();
    },
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
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">MRR</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-semibold">{indicateurs?.mrr != null ? fmtEuro(indicateurs.mrr) : "—"}</p></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">ARR (×12)</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-semibold">{indicateurs?.arr != null ? fmtEuro(indicateurs.arr) : "—"}</p></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Actifs</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-semibold">{indicateurs?.actifs ?? "—"}</p></CardContent></Card>
      </div>

      <ResourcePage
        titre="Abonnements"
        endpoint="subscriptions/subscriptions/"
        colonnes={[
          { key: "client_name", label: "Client" },
          { key: "label", label: "Offre" },
          { key: "billing_period", label: "Périodicité" },
          { key: "amount", label: "Montant" },
          { key: "next_billing_date", label: "Prochaine échéance" },
          { key: "status", label: "Statut", render: (s: any) => <Badge variant={STATUTS[s.status] ?? "muted"}>{s.status}</Badge> },
        ]}
        champs={[
          { name: "client", label: "Client", type: "select", optionsUrl: "invoicing/clients/", required: true },
          { name: "label", label: "Intitulé de l'offre", required: true },
          { name: "amount", label: "Montant HT", type: "number", step: "0.01", required: true },
          { name: "billing_period", label: "Périodicité", type: "select", required: true, options: [
            { value: "mensuel", label: "Mensuel" }, { value: "trimestriel", label: "Trimestriel" }, { value: "annuel", label: "Annuel" },
          ]},
          { name: "start_date", label: "Début", type: "date", required: true },
          { name: "end_date", label: "Fin (optionnel)", type: "date" },
        ]}
      />
    </div>
  );
}
