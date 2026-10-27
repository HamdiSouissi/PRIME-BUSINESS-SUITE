import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Check, X } from "lucide-react";

const VARIANTES: Record<string, any> = {
  soumise: "warning",
  approuvee: "success",
  refusee: "danger",
};

export default function AbsencesPage() {
  const qc = useQueryClient();
  const agir = useMutation<any, unknown, { id: number; action: "approve" | "reject" }>({
    mutationFn: ({ id, action }: { id: number; action: "approve" | "reject" }) =>
      api.post(`hr/leave-requests/${id}/${action}/`, {}),
    onSuccess: (_d, v) => {
      toast.success(v.action === "approve" ? "Absence approuvée." : "Absence refusée.");
      qc.invalidateQueries({ queryKey: ["hr/leave-requests/"] });
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
          { key: "leave_type_name", label: "Type" },
          { key: "start_date", label: "Du" },
          { key: "end_date", label: "Au" },
          {
            key: "status", label: "Statut",
            render: (r: any) => <Badge variant={VARIANTES[r.status] ?? "muted"}>{r.status}</Badge>,
          },
        ]}
        champs={[
          { name: "employee", label: "Salarié", type: "select", optionsUrl: "hr/employees/", required: true },
          { name: "leave_type", label: "Type", type: "select", optionsUrl: "hr/leave-types/", required: true },
          { name: "start_date", label: "Début", type: "date", required: true },
          { name: "end_date", label: "Fin", type: "date", required: true },
          { name: "reason", label: "Motif", type: "textarea" },
        ]}
        actions={(r: any) =>
          r.status === "soumise" ? (
            <>
              <Button size="icon" variant="ghost" title="Approuver"
                onClick={() => agir.mutate({ id: r.id, action: "approve" })}>
                <Check className="h-4 w-4 text-emerald-600" />
              </Button>
              <Button size="icon" variant="ghost" title="Refuser"
                onClick={() => {
                  const motif = window.prompt("Motif du refus (obligatoire) :");
                  if (motif) agir.mutate({ id: r.id, action: "reject", } as any);
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
