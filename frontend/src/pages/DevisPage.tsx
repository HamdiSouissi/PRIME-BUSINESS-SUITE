import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ArrowRightLeft, SendHorizontal } from "lucide-react";

const STATUTS: Record<string, any> = {
  brouillon: "muted", envoye: "info", accepte: "success", refuse: "danger", expire: "muted", converti: "warning",
};

export default function DevisPage() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["invoicing/quotes/"] });

  const agir = useMutation<any, unknown, { id: number; act: string }>({
    mutationFn: ({ id, act }: { id: number; act: string }) =>
      api.post(`invoicing/quotes/${id}/${act}/`, {}),
    onSuccess: (_d, v) => {
      toast.success(v.act === "convertir" ? "Facture générée (conversion idempotente)." : "Devis mis à jour.");
      refresh();
    },
    onError: notifierErreur,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Devis</h1>
      <p className="text-sm text-muted-foreground">
        Un devis accepté peut être converti en facture — une seule fois (anti double-conversion).
      </p>
      <ResourcePage
        titre="Devis"
        endpoint="invoicing/quotes/"
        colonnes={[
          { key: "number", label: "N°" },
          { key: "client_name", label: "Client" },
          { key: "issue_date", label: "Émis le" },
          { key: "total_ttc", label: "Total TTC" },
          { key: "status", label: "Statut", render: (q: any) => <Badge variant={STATUTS[q.status] ?? "muted"}>{q.status}</Badge> },
        ]}
        champs={[
          { name: "client", label: "Client", type: "select", optionsUrl: "invoicing/clients/", required: true },
          { name: "issue_date", label: "Date d'émission", type: "date", required: true },
          { name: "validity_date", label: "Valable jusqu'au", type: "date" },
          { name: "notes", label: "Notes", type: "textarea" },
        ]}
        actions={(q: any) => (
          <>
            {q.status === "brouillon" && (
              <Button size="icon" variant="ghost" title="Marquer envoyé"
                onClick={() => agir.mutate({ id: q.id, act: "envoyer" })}>
                <SendHorizontal className="h-4 w-4" />
              </Button>
            )}
            {(q.status === "accepte" || q.status === "envoye") && (
              <Button size="icon" variant="ghost" title="Convertir en facture"
                onClick={() => agir.mutate({ id: q.id, act: "convertir" })}>
                <ArrowRightLeft className="h-4 w-4" />
              </Button>
            )}
          </>
        )}
      />
    </div>
  );
}
