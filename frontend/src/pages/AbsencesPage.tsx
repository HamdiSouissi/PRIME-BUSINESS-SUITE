import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Check, X } from "lucide-react";

const VARIANTES: Record<string, any> = {
  brouillon: "muted",
  soumise: "warning",
  validee: "success",
  refusee: "danger",
  annulee: "muted",
};

export default function AbsencesPage() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["hr/leave-requests/"] });

  const decider = useMutation<any, unknown, { id: number; decision: "validee" | "refusee"; commentaire?: string }>({
    mutationFn: ({ id, decision, commentaire }) =>
      api.post(`hr/leave-requests/${id}/decision/`, { decision, commentaire: commentaire ?? "" }),
    onSuccess: (_d, v) => {
      toast.success(v.decision === "validee" ? "Absence validée." : "Absence refusée.");
      refresh();
    },
    onError: notifierErreur,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Congés & absences</h1>
      <p className="text-sm text-muted-foreground">
        Soumises par le salarié via son portail, puis tranchées par le manager ou RH. Les motifs de refus sont tracés.
      </p>
      <ResourcePage
        titre="Demandes d'absence"
        endpoint="hr/leave-requests/"
        colonnes={[
          { key: "employee_name", label: "Salarié" },
          { key: "leave_type_label", label: "Type" },
          { key: "start_date", label: "Du" },
          { key: "end_date", label: "Au" },
          {
            key: "status", label: "Statut",
            render: (r: any) => <Badge variant={VARIANTES[r.status] ?? "muted"}>{r.status_label ?? r.status}</Badge>,
          },
        ]}
        champs={[
          { name: "employee", label: "Salarié", type: "select", optionsUrl: "hr/employees/", required: true },
          { name: "leave_type", label: "Type", type: "select", optionsUrl: "hr/leave-types/", required: true },
          { name: "start_date", label: "Début", type: "date", required: true },
          { name: "end_date", label: "Fin", type: "date", required: true },
          { name: "comment", label: "Commentaire", type: "textarea" },
        ]}
        actions={(r: any) =>
          r.status === "soumise" ? (
            <>
              <Button size="icon" variant="ghost" title="Valider"
                onClick={() => decider.mutate({ id: r.id, decision: "validee" })}>
                <Check className="h-4 w-4 text-emerald-600" />
              </Button>
              <Button size="icon" variant="ghost" title="Refuser"
                onClick={() => {
                  const commentaire = window.prompt("Motif du refus (obligatoire) :");
                  if (commentaire) decider.mutate({ id: r.id, decision: "refusee", commentaire });
                }}>
                <X className="h-4 w-4 text-destructive" />
              </Button>
            </>
          ) : null
        }
      />
    </div>
  );
}
