import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { TBody, THead, Table, Td, Th, Tr } from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs } from "@/components/ui/tabs";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmtEuro } from "@/lib/utils";

function Budgets() {
  return (
    <ResourcePage
      titre="Budgets"
      description="Chargez des lignes budgetaires puis comparez au réel — écart calculé en valeur et %."
      endpoint="budgets/budgets/"
      colonnes={[
        { key: "name", label: "Nom" },
        { key: "year", label: "Année" },
        { key: "status", label: "Statut", render: (b: any) => <Badge variant={b.status === "actif" ? "success" : "muted"}>{b.status}</Badge> },
      ]}
      champs={[
        { name: "name", label: "Nom", required: true },
        { name: "year", label: "Année", type: "number", required: true },
      ]}
    />
  );
}

function Lignes() {
  const { data } = useQuery({
    queryKey: ["budgets/lines/"],
    queryFn: async () => {
      const res = await api.get("budgets/lines/");
      const d = res.data;
      return Array.isArray(d) ? d : d.results ?? [];
    },
  });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Budget vs Réel</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <THead><Tr><Th>Compte</Th><Th>Budget</Th><Th>Réel</Th><Th>Écart</Th><Th>%</Th></Tr></THead>
          <TBody>
            {(data ?? []).map((l: any) => (
              <Tr key={l.id}>
                <Td>{l.account_code ?? l.account}</Td>
                <Td>{fmtEuro(l.budgeted)}</Td>
                <Td>{fmtEuro(l.actual)}</Td>
                <Td className={Number(l.variance) < 0 ? "text-destructive font-medium" : "text-emerald-600"}>{fmtEuro(l.variance)}</Td>
                <Td>{l.variance_pct != null ? `${Number(l.variance_pct).toFixed(1)} %` : "—"}</Td>
              </Tr>
            ))}
          </TBody>
        </Table>
        {!(data ?? []).length && <p className="py-4 text-sm text-muted-foreground">Aucune ligne budgétaire.</p>}
      </CardContent>
    </Card>
  );
}

export default function BudgetsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Budgets & pilotage</h1>
      <p className="text-sm text-muted-foreground">
        Écart = Réel − Budget (les pourcentages n'ont de sens que sur les postes dotés d'un budget).
      </p>
      <Tabs onglets={[
        { id: "budgets", label: "Budgets", contenu: <Budgets /> },
        { id: "analyse", label: "Budget vs Réel", contenu: <Lignes /> },
      ]} />
    </div>
  );
}
