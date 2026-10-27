import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { CheckCircle2, SendHorizontal, XCircle, Banknote } from "lucide-react";

const STATUTS: Record<string, any> = {
  brouillon: "muted", soumise: "warning", validee: "success", refusee: "danger",
  remboursee: "success", comptabilisee: "info",
};

export default function DepensesPage() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["expenses/reports/"] });

  const agir = useMutation<any, unknown, { id: number; act: string; motif?: string }>({
    mutationFn: ({ id, act, motif }: { id: number; act: string; motif?: string }) =>
      api.post(`expenses/reports/${id}/${act}/`, motif ? { motif } : {}),
    onSuccess: (_d, v) => { toast.success("Action effectuée."); refresh(); },
    onError: notifierErreur,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Notes de frais</h1>
      <p className="text-sm text-muted-foreground">
        Circuit : brouillon → soumise → validée ou refusée (motif obligatoire) → remboursée. Tout dépassement
        de l'autorisation est tracé (override).
      </p>
      <ResourcePage
        titre="Notes de frais"
        endpoint="expenses/reports/"
        colonnes={[
          { key: "employee_name", label: "Salarié" },
          { key: "title", label: "Intitulé" },
          { key: "period", label: "Période" },
          { key: "total", label: "Total (€)" },
          { key: "status", label: "Statut", render: (r: any) => <Badge variant={STATUTS[r.status] ?? "muted"}>{r.status}</Badge> },
        ]}
        champs={[
          { name: "title", label: "Intitulé", required: true },
          { name: "period", label: "Période (ex. 10/2026)", required: true },
          { name: "employee", label: "Salarié", type: "select", optionsUrl: "hr/employees/" },
        ]}
        actions={(r: any, refresh) => (
          <>
            {r.status === "brouillon" && (
              <Button size="icon" variant="ghost" title="Soumettre"
                onClick={() => agir.mutate({ id: r.id, act: "soumettre" })}>
                <SendHorizontal className="h-4 w-4" />
              </Button>
            )}
            {r.status === "soumise" && (
              <>
                <Button size="icon" variant="ghost" title="Valider"
                  onClick={() => agir.mutate({ id: r.id, act: "decision" })}>
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                </Button>
                <Button size="icon" variant="ghost" title="Refuser"
                  onClick={() => {
                    const motif = window.prompt("Motif de refus (obligatoire) :");
                    if (motif) agir.mutate({ id: r.id, act: "decision", motif: `REFUS:${motif}` });
                  }}>
                  <XCircle className="h-4 w-4 text-destructive" />
                </Button>
              </>
            )}
            {r.status === "validee" && (
              <Button size="icon" variant="ghost" title="Marquer remboursée"
                onClick={() => agir.mutate({ id: r.id, act: "remboursee" })}>
                <Banknote className="h-4 w-4" />
              </Button>
            )}
          </>
        )}
      />
    </div>
  );
}
