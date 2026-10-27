import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs } from "@/components/ui/tabs";
import { toast } from "sonner";
import { BellRing } from "lucide-react";

function Associes() {
  return (
    <ResourcePage
      titre="Associés"
      description="Aucun associé n'a de droit implicite à des dividendes — tout versement requiert une décision validée."
      endpoint="dividends/associates/"
      colonnes={[
        { key: "first_name", label: "Prénom" },
        { key: "last_name", label: "Nom" },
        { key: "email", label: "Email" },
        { key: "shares", label: "Parts" },
        { key: "pct_capital", label: "% capital" },
      ]}
      champs={[
        { name: "first_name", label: "Prénom", required: true },
        { name: "last_name", label: "Nom", required: true },
        { name: "email", label: "Email", type: "email" },
        {
          name: "is_company", label: "Personne morale", type: "select",
          options: [{ value: "false", label: "Personne physique" }, { value: "true", label: "Personne morale" }],
        },
        { name: "company_name", label: "Raison sociale (si morale)" },
        { name: "shares", label: "Nombre de parts", type: "number", required: true },
        { name: "entry_date", label: "Date d'entrée au capital", type: "date", required: true },
        { name: "exit_date", label: "Date de sortie", type: "date" },
        { name: "notes", label: "Notes", type: "textarea" },
      ]}
    />
  );
}

function Distributions() {
  const qc = useQueryClient();
  // Workflow réel : projet -> decidee via l'action « decider » (pas d'action « valider »).
  const decider = useMutation<any, unknown, { id: number; montant: number | string }>({
    mutationFn: ({ id, montant }) => api.post(`dividends/distributions/${id}/decider/`, { montant }),
    onSuccess: () => {
      toast.success("Décision enregistrée (sans automatisation de paiement).");
      qc.invalidateQueries({ queryKey: ["dividends/distributions/"] });
    },
    onError: notifierErreur,
  });
  return (
    <ResourcePage
      titre="Décisions de distribution"
      description="Circuit : projet → décision en assemblée → paiement séparé. Aucun virement automatique."
      endpoint="dividends/distributions/"
      colonnes={[
        { key: "fiscal_year", label: "Exercice" },
        { key: "meeting_date", label: "AG" },
        { key: "montant_decide", label: "Montant décidé" },
        { key: "somme_distribuable", label: "Distribuable" },
        { key: "status", label: "Statut", render: (d: any) => <Badge variant={d.status === "payee" ? "success" : "warning"}>{d.status_label ?? d.status}</Badge> },
      ]}
      champs={[
        { name: "fiscal_year", label: "Exercice concerné (année)", type: "number", required: true },
        { name: "meeting_date", label: "Date d'assemblée générale", type: "date", required: true },
        { name: "resultat_exercice", label: "Résultat de l'exercice (€)", type: "number", step: "0.01", required: true },
        { name: "report_a_nouveau", label: "Report à nouveau (€)", type: "number", step: "0.01" },
        { name: "autres_reserves", label: "Autres réserves distribuables (€)", type: "number", step: "0.01" },
        { name: "montant_decide", label: "Montant décidé (€)", type: "number", step: "0.01" },
        { name: "withholding_rate", label: "Taux de retenue (%)", type: "number", step: "0.01" },
        { name: "notes", label: "Notes", type: "textarea" },
      ]}
      actions={(d: any) => (
        <>
          {d.status === "projet" && (
            <Button
              size="icon"
              variant="ghost"
              title="Décider en assemblée"
              onClick={() => decider.mutate({ id: d.id, montant: d.montant_decide ?? 0 })}
            >
              <BellRing className="h-4 w-4" />
            </Button>
          )}
        </>
      )}
    />
  );
}

export default function AssociesPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Associés & dividendes</h1>
      <Tabs onglets={[
        { id: "associes", label: "Associés", contenu: <Associes /> },
        { id: "distributions", label: "Distributions", contenu: <Distributions /> },
      ]} />
    </div>
  );
}
