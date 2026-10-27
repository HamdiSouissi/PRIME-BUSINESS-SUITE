import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs } from "@/components/ui/tabs";
import { TBody, THead, Table, Td, Th, Tr } from "@/components/ui/table";
import { fmtEuro } from "@/lib/utils";
import { Alerte } from "@/components/ui/modal";
import { toast } from "sonner";
import { Lock, Download, CheckCircle2, Undo2 } from "lucide-react";

function Balance() {
  const { data } = useQuery({
    queryKey: ["balance"],
    queryFn: async () => (await api.get("accounting/entries/balance/")).data,
  });
  const lignes = data?.balance ?? data?.lignes ?? [];
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Balance des comptes</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <THead><Tr><Th>Compte</Th><Th>Libellé</Th><Th className="text-right">Débit</Th><Th className="text-right">Crédit</Th></Tr></THead>
          <TBody>
            {lignes.map((l: any, i: number) => (
              <Tr key={i}><Td className="font-mono">{l.number ?? l.code}</Td><Td>{l.label}</Td>
                <Td className="text-right">{fmtEuro(l.debit)}</Td><Td className="text-right">{fmtEuro(l.credit)}</Td></Tr>
            ))}
          </TBody>
        </Table>
        {!lignes.length && <p className="py-4 text-sm text-muted-foreground">Aucune écriture.</p>}
      </CardContent>
    </Card>
  );
}

function Ecritures() {
  const qc = useQueryClient();
  const agir = useMutation<any, unknown, { id: number; act: "valider" | "contre-passer" }>({
    mutationFn: ({ id, act }: { id: number; act: "valider" | "contre-passer" }) =>
      api.post(`accounting/entries/${id}/${act}/`, {}),
    onSuccess: (_d, v) => {
      toast.success(v.act === "valider" ? "Écriture validée (ne pourra plus être modifiée)." : "Contre-écriture créée.");
      qc.invalidateQueries({ queryKey: ["accounting/entries/"] });
    },
    onError: notifierErreur,
  });
  return (
    <ResourcePage
      titre="Écritures comptables"
      description="Une fois validée, une écriture devient immuable : la correction se fait par contre-écriture."
      endpoint="accounting/entries/"
      colonnes={[
        { key: "id", label: "N°" }, { key: "date", label: "Date" },
        { key: "journal_code", label: "Journal" }, { key: "label", label: "Libellé" },
        { key: "total_debit", label: "Débit" }, { key: "total_credit", label: "Crédit" },
        { key: "status", label: "Statut", render: (e: any) => <Badge variant={e.status === "validee" ? "success" : e.status === "contre_passee" ? "muted" : "warning"}>{e.status_label ?? e.status}</Badge> },
      ]}
      champs={[
        { name: "journal", label: "Journal", type: "select", optionsUrl: "accounting/journals/", required: true },
        { name: "date", label: "Date", type: "date", required: true },
        { name: "label", label: "Libellé", required: true },
      ]}
      actions={(e: any) => e.status === "brouillon" ? (
        <Button size="icon" variant="ghost" title="Valider" onClick={() => agir.mutate({ id: e.id, act: "valider" })}>
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        </Button>
      ) : e.status === "validee" ? (
        <Button size="icon" variant="ghost" title="Contre-passer" onClick={() => agir.mutate({ id: e.id, act: "contre-passer" })}>
          <Undo2 className="h-4 w-4" />
        </Button>
      ) : null}
    />
  );
}

function PlanComptable() {
  const qc = useQueryClient();
  const initPlan = useMutation<any, unknown, void>({
    mutationFn: () => api.post("accounting/accounts/plan-par-defaut/", {}),
    onSuccess: () => { toast.success("Plan comptable par défaut chargé (PCG simplifié)."); qc.invalidateQueries(); },
    onError: notifierErreur,
  });
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button variant="outline" onClick={() => initPlan.mutate()}>Charger le plan par défaut</Button>
      </div>
      <ResourcePage
        titre="Plan comptable"
        description="Configurable par entreprise. Rien n'est imposé par le code."
        endpoint="accounting/accounts/"
        colonnes={[
          { key: "number", label: "Numéro", render: (a: any) => <span className="font-mono">{a.number}</span> },
          { key: "label", label: "Libellé" },
          { key: "account_class", label: "Classe" },
          { key: "account_type", label: "Type" },
          { key: "is_active", label: "Actif", render: (a: any) => <Badge variant={a.is_active ? "success" : "muted"}>{a.is_active ? "Oui" : "Non"}</Badge> },
        ]}
        champs={[
          { name: "number", label: "Numéro de compte", required: true },
          { name: "label", label: "Libellé", required: true },
          { name: "account_class", label: "Classe PCG (1-8)", required: true },
          { name: "account_type", label: "Type de compte", type: "select", options: [
            { value: "general", label: "Compte général" },
            { value: "client", label: "Auxiliaire client" },
            { value: "fournisseur", label: "Auxiliaire fournisseur" },
            { value: "banque", label: "Bancaire" },
            { value: "caisse", label: "Caisse" },
          ]},
        ]}
      />
    </div>
  );
}

function Exercices() {
  const qc = useQueryClient();
  const agir = useMutation<any, unknown, { id: number; act: "verrouiller" | "cloturer" }>({
    mutationFn: ({ id, act }: { id: number; act: "verrouiller" | "cloturer" }) =>
      api.post(`accounting/fiscal-years/${id}/${act}/`, {}),
    onSuccess: (_d, v) => { toast.success(v.act === "verrouiller" ? "Exercice verrouillé." : "Exercice clôturé."); qc.invalidateQueries(); },
    onError: notifierErreur,
  });
  return (
    <ResourcePage
      titre="Exercices comptables"
      endpoint="accounting/fiscal-years/"
      colonnes={[
        { key: "start_date", label: "Début" },
        { key: "end_date", label: "Fin" },
        { key: "status", label: "Statut", render: (y: any) => <Badge variant={y.status === "cloture" ? "muted" : y.status === "verrouille" ? "warning" : "success"}>{y.status}</Badge> },
      ]}
      champs={[
        { name: "start_date", label: "Début", type: "date", required: true },
        { name: "end_date", label: "Fin", type: "date", required: true },
      ]}
      actions={(y: any) => y.status === "ouvert" ? (
        <>
          <Button size="icon" variant="ghost" title="Verrouiller (plus d'écriture)"
            onClick={() => agir.mutate({ id: y.id, act: "verrouiller" })}>
            <Lock className="h-4 w-4" />
          </Button>
        </>
      ) : y.status === "verrouille" ? (
        <Button size="icon" variant="ghost" title="Clôturer définitivement"
          onClick={() => { if (window.confirm("Clôturer définitivement cet exercice ?")) agir.mutate({ id: y.id, act: "cloturer" }); }}>
          <Lock className="h-4 w-4 text-destructive" />
        </Button>
      ) : null}
    />
  );
}

export default function ComptabilitePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Comptabilité</h1>
      <Alerte variante="warning">
        Export « préparé pour expert-comptable » disponible (FEC-like) — <strong>non certifié</strong>. Votre
        cabinet reste responsable de la validation fiscale définitive.
      </Alerte>
      <Tabs onglets={[
        { id: "ecritures", label: "Écritures", contenu: <Ecritures /> },
        { id: "balance", label: "Balance", contenu: <Balance /> },
        { id: "plan", label: "Plan comptable", contenu: <PlanComptable /> },
        { id: "exercices", label: "Exercices", contenu: <Exercices /> },
      ]} />
    </div>
  );
}
