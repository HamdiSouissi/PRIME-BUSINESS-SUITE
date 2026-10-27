import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs } from "@/components/ui/tabs";
import { TBody, THead, Table, Td, Th, Tr } from "@/components/ui/table";
import { fmtEuro } from "@/lib/utils";
import { Alerte } from "@/components/ui/modal";

function Synthese() {
  const { data } = useQuery({
    queryKey: ["treso-synthese"],
    queryFn: async () => (await api.get("treasury/transactions/synthese/")).data,
  });
  const { data: previ } = useQuery({
    queryKey: ["treso-previ"],
    queryFn: async () => (await api.get("treasury/transactions/previsionnel/")).data,
  });
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Solde bancaire</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-semibold">{fmtEuro(data?.solde_bancaire_total)}</p>
            <p className="text-xs text-muted-foreground">Somme des comptes rapprochés (rien n'est « débité » réellement).</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Solde comptable (512)</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-semibold">{fmtEuro(data?.solde_comptable_512)}</p>
            <p className="text-xs text-muted-foreground">Écritures — distinct du bancaire ; rapprochement dédié.</p></CardContent>
        </Card>
      </div>
      <Alerte variante="info">
        L'application ne pilote jamais de virement réel. Elle prépare des fichiers/listes et calcule des prévisions :
        aucune banque n'est connectée en écriture.
      </Alerte>
      <Card>
        <CardHeader><CardTitle className="text-base">Prévisionnel (définitions documentées)</CardTitle></CardHeader>
        <CardContent>
          {!previ ? <p className="text-sm text-muted-foreground">—</p> : (
            <Table>
              <THead><Tr><Th>Horizon</Th><Th>Entrées</Th><Th>Sorties</Th><Th>Nets</Th></Tr></THead>
              <TBody>
                {(previ.lignes ?? previ ?? []).map((l: any) => (
                  <Tr key={l.horizon}>
                    <Td>{l.horizon}</Td><Td>{fmtEuro(l.entrees)}</Td><Td>{fmtEuro(l.sorties)}</Td>
                    <Td className="font-medium">{fmtEuro(l.solde)}</Td>
                  </Tr>
                ))}
              </TBody>
            </Table>
          )}
          <p className="mt-2 text-xs text-muted-foreground">
            Horizons 30/60/90/180 j, scénarios prudents/central/optimiste réglables côté paramétrage — sources d'hypothèses saisies par vos soins.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export default function TresoreriePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Trésorerie</h1>
      <Tabs onglets={[
        { id: "synthese", label: "Synthèse & prévisionnel", contenu: <Synthese /> },
        {
          id: "comptes", label: "Comptes bancaires",
          contenu: (
            <ResourcePage
              titre="Comptes bancaires"
              endpoint="treasury/bank-accounts/"
              colonnes={[
                { key: "label", label: "Libellé" }, { key: "bank_name", label: "Banque" },
                { key: "iban", label: "IBAN" },
                { key: "is_active", label: "Statut", render: (c: any) => <Badge variant={c.is_active ? "success" : "muted"}>{c.is_active ? "Actif" : "Inactif"}</Badge> },
              ]}
              champs={[
                { name: "label", label: "Libellé", required: true },
                { name: "bank_name", label: "Banque", required: true },
                { name: "iban", label: "IBAN" },
                { name: "bic", label: "BIC" },
              ]}
            />
          ),
        },
        {
          id: "transactions", label: "Transactions",
          contenu: (
            <ResourcePage
              titre="Transactions bancaires"
              description="Import CSV avec déduplication. Rapprochement via l'action dédiée côté API."
              endpoint="treasury/transactions/"
              colonnes={[
                { key: "bank_account_name", label: "Compte" }, { key: "date", label: "Date" },
                { key: "label", label: "Libellé" }, { key: "amount", label: "Montant" },
                { key: "reconciled", label: "Rapprochée", render: (t: any) => <Badge variant={t.reconciled ? "success" : "warning"}>{t.reconciled ? "Oui" : "Non"}</Badge> },
              ]}
              champs={[
                { name: "bank_account", label: "Compte", type: "select", optionsUrl: "treasury/bank-accounts/", required: true },
                { name: "date", label: "Date", type: "date", required: true },
                { name: "label", label: "Libellé", required: true },
                { name: "amount", label: "Montant (+ entrée / − sortie)", type: "number", step: "0.01", required: true },
              ]}
            />
          ),
        },
      ]} />
    </div>
  );
}
