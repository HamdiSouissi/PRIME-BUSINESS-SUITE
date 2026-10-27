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
      description="Chargez des lignes budgétaires puis comparez au réel — écart calculé en valeur et %."
      endpoint="budgets/budgets/"
      colonnes={[
        { key: "label", label: "Nom" },
        { key: "year", label: "Année" },
        { key: "is_active", label: "Statut", render: (b: any) => <Badge variant={b.is_active ? "success" : "muted"}>{b.is_active ? "Actif" : "Inactif"}</Badge> },
      ]}
      champs={[
        { name: "label", label: "Nom du budget", required: true },
        { name: "year", label: "Année", type: "number", required: true },
        {
          name: "is_active", label: "Statut", type: "select",
          options: [{ value: "true", label: "Actif" }, { value: "false", label: "Inactif" }],
        },
        { name: "hypotheses", label: "Hypothèses", type: "textarea" },
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
      <CardHeader><CardTitle className="text-base">Lignes budgétaires</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <THead><Tr><Th>Libellé</Th><Th>Nature</Th><Th>Préfixe compte</Th><Th>Total annuel</Th></Tr></THead>
          <TBody>
            {(data ?? []).map((l: any) => (
              <Tr key={l.id}>
                <Td>{l.label}</Td>
                <Td>{l.nature_label ?? l.nature}</Td>
                <Td>{l.account_prefix || "—"}</Td>
                <Td>{fmtEuro(l.total_annuel)}</Td>
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
        Le réalisé est rapproché via les préfixes de compte comptable (action d'analyse d'un budget).
      </p>
      <Tabs onglets={[
        { id: "budgets", label: "Budgets", contenu: <Budgets /> },
        { id: "analyse", label: "Lignes", contenu: <Lignes /> },
      ]} />
    </div>
  );
}
