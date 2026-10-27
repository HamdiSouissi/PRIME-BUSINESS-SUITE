import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs } from "@/components/ui/tabs";
import { toast } from "sonner";
import { BellRing, CheckCircle2 } from "lucide-react";

function Associes() {
  return (
    <ResourcePage
      titre="Associés"
      description="Aucun associé n'a de droit implicite à des dividendes — tout versement requiert une décision validée."
      endpoint="dividends/associates/"
      colonnes={[
        { key: "name", label: "Nom" },
        { key: "email", label: "Email" },
        { key: "shares_count", label: "Parts" },
        { key: "ownership_pct", label: "% capital" },
      ]}
      champs={[
        { name: "name", label: "Nom", required: true },
        { name: "email", label: "Email", type: "email" },
        { name: "shares_count", label: "Nombre de parts", type: "number", required: true },
      ]}
    />
  );
}

function Distributions() {
  const qc = useQueryClient();
  const agir = useMutation<any, unknown, { id: number; act: "decider" | "valider" }>({
    mutationFn: ({ id, act }: { id: number; act: "decider" | "valider" }) =>
      api.post(`dividends/distributions/${id}/${act}/`, {}),
    onSuccess: (_d, v) => {
      toast.success(v.act === "decider" ? "Décision enregistrée (sans automatisation de paiement)." : "Distribution validée.");
      qc.invalidateQueries({ queryKey: ["dividends/distributions/"] });
    },
    onError: notifierErreur,
  });
  return (
    <ResourcePage
      titre="Décisions de distribution"
      description="Circuit : proposition → décision → validation → notification aux associés. Aucun virement automatique."
      endpoint="dividends/distributions/"
      colonnes={[
        { key: "reference", label: "Réf." },
        { key: "title", label: "Objet" },
        { key: "total_amount", label: "Montant" },
        { key: "status", label: "Statut", render: (d: any) => <Badge variant={d.status === "validee" ? "success" : "warning"}>{d.status}</Badge> },
      ]}
      champs={[
        { name: "title", label: "Objet de la décision", required: true },
        { name: "total_amount", label: "Montant total (€)", type: "number", step: "0.01", required: true },
        { name: "meeting_date", label: "Date d'AG", type: "date", required: true },
      ]}
      actions={(d: any) => (
        <>
          {d.status === "brouillon" && (
            <Button size="icon" variant="ghost" title="Décider" onClick={() => agir.mutate({ id: d.id, act: "decider" })}>
              <BellRing className="h-4 w-4" />
            </Button>
          )}
          {d.status === "decidee" && (
            <Button size="icon" variant="ghost" title="Valider" onClick={() => agir.mutate({ id: d.id, act: "valider" })}>
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
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
