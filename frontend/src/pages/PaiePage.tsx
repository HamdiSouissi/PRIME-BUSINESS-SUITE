import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alerte, Modal } from "@/components/ui/modal";
import { Input, Label } from "@/components/ui/input";
import { TBody, THead, Table, Td, Th, Tr } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { fmtEuro } from "@/lib/utils";
import { toast } from "sonner";

const STATUTS: Record<string, any> = {
  brouillon: "muted", simulee: "info", validee: "success", cloturee: "warning", payee: "success",
};

function useRuns() {
  return useQuery({
    queryKey: ["payroll/runs/"],
    queryFn: async () => {
      const res = await api.get("payroll/runs/");
      const d = res.data;
      return Array.isArray(d) ? d : d.results ?? [];
    },
  });
}

function Anomalies({ runId }: { runId: number }) {
  const { data } = useQuery({
    queryKey: ["anomalies", runId],
    queryFn: async () => (await api.get(`payroll/runs/${runId}/anomalies/`)).data,
  });
  if (!data) return null;
  const anomalies = data.anomalies ?? data;
  if (!anomalies.length) return <Alerte variante="success">Aucune anomalie bloquante détectée.</Alerte>;
  return (
    <div className="space-y-2">
      <Alerte variante="danger">
        Validation définitive bloquée tant que les anomalies ci-dessous ne sont pas corrigées.
      </Alerte>
      <ul className="list-disc space-y-1 pl-5 text-sm">
        {anomalies.map((a: any, i: number) => (
          <li key={i}>
            <span className="font-medium">{a.employee ?? a.salarie ?? ""}</span> — {a.message ?? a.detail ?? JSON.stringify(a)}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function PaiePage() {
  const qc = useQueryClient();
  const [nouveau, setNouveau] = useState(false);
  const [mois, setMois] = useState("");
  const [annee, setAnnee] = useState("");
  const { data: runs } = useRuns();

  const creerRun = useMutation<any, unknown, void>({
    mutationFn: () => api.post("payroll/runs/", { period_month: Number(mois), period_year: Number(annee) }),
    onSuccess: () => { toast.success("Lot de paie créé."); setNouveau(false); qc.invalidateQueries({ queryKey: ["payroll/runs/"] }); },
    onError: notifierErreur,
  });

  const action = useMutation<any, unknown, { id: number; act: "simuler" | "valider" | "cloturer" | "dsn" | "editer-bulletins" }>({
    mutationFn: ({ id, act }: { id: number; act: "simuler" | "valider" | "cloturer" | "dsn" | "editer-bulletins" }) =>
      api.post(`payroll/runs/${id}/${act}/`, {}),
    onSuccess: (_d, v) => {
      toast.success(
        v.act === "valider" ? "Lot validé définitivement."
        : v.act === "dsn" ? "DSN générée (fichier préparé — NON transmis, NON certifié)."
        : v.act === "editer-bulletins" ? "Bulletins PDF générés."
        : `Action "${v.act}" effectuée.`
      );
      qc.invalidateQueries({ queryKey: ["payroll/runs/"] });
    },
    onError: notifierErreur,
  });

  const { data: params } = useQuery({
    queryKey: ["payroll-params"],
    queryFn: async () => {
      const res = await api.get("payroll/parameter-sets/");
      const d = res.data;
      return Array.isArray(d) ? d : d.results ?? [];
    },
  });
  const paramNonVerifie = (params ?? []).some((p: any) => !p.verified);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Paie</h1>
          <p className="text-sm text-muted-foreground">
            Moteur de règles versionnées — aucun taux codé en dur. Sources officielles à documenter dans chaque jeu de paramètres.
          </p>
        </div>
        <Button onClick={() => setNouveau(true)}>Nouveau lot de paie</Button>
      </div>

      {paramNonVerifie && (
        <Alerte variante="warning">
          Au moins un jeu de paramètres n'est pas marqué « vérifié ». La validation définitive des lots est
          bloquée tant que les règles applicables ne sont pas vérifiées (sources + dates d'effet).
        </Alerte>
      )}

      <Tabs onglets={[
        {
          id: "lots", label: "Lots de paie",
          contenu: (
            <Card>
              <CardHeader><CardTitle className="text-base">Historique des lots</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <THead><Tr><Th>Période</Th><Th>Statut</Th><Th>Brut</Th><Th>Net à payer</Th><Th>Charges</Th><Th className="w-72 text-right">Actions</Th></Tr></THead>
                  <TBody>
                    {(runs ?? []).map((r: any) => (
                      <Tr key={r.id}>
                        <Td>{String(r.period_month).padStart(2, "0")}/{r.period_year}</Td>
                        <Td><Badge variant={STATUTS[r.status] ?? "muted"}>{r.status}</Badge></Td>
                        <Td>{fmtEuro(r.total_brut)}</Td>
                        <Td>{fmtEuro(r.total_net)}</Td>
                        <Td>{fmtEuro((r.total_cotisations_salariales ?? 0) + (r.total_cotisations_patronales ?? 0))}</Td>
                        <Td className="text-right">
                          <div className="flex justify-end gap-1">
                            {(r.status === "brouillon" || r.status === "simulee") && (
                              <Button size="sm" variant="outline" onClick={() => action.mutate({ id: r.id, act: "simuler" })}>Simuler</Button>
                            )}
                            {r.status === "simulee" && (
                              <Button size="sm" onClick={() => action.mutate({ id: r.id, act: "valider" })}>Valider</Button>
                            )}
                            {r.status === "validee" && (
                              <>
                                <Button size="sm" variant="outline" onClick={() => action.mutate({ id: r.id, act: "editer-bulletins" })}>Bulletins PDF</Button>
                                <Button size="sm" variant="outline" onClick={() => action.mutate({ id: r.id, act: "dsn" })}>DSN</Button>
                                <Button size="sm" variant="outline" onClick={() => action.mutate({ id: r.id, act: "cloturer" })}>Clôturer</Button>
                              </>
                            )}
                          </div>
                        </Td>
                      </Tr>
                    ))}
                  </TBody>
                </Table>
                {!(runs ?? []).length && <p className="py-6 text-center text-sm text-muted-foreground">Aucun lot créé.</p>}
              </CardContent>
            </Card>
          ),
        },
        {
          id: "anomalies", label: "Anomalies du dernier lot",
          contenu: (runs ?? []).length ? (
            <Card><CardHeader><CardTitle className="text-base">Contrôle avant validation</CardTitle></CardHeader>
            <CardContent><Anomalies runId={(runs ?? [])[0].id} /></CardContent></Card>
          ) : <p className="text-sm text-muted-foreground">Aucun lot.</p>,
        },
        {
          id: "params", label: "Jeux de paramètres",
          contenu: (
            <Card>
              <CardHeader><CardTitle className="text-base">Paramètres de paie (versionnés, datés, sourcés)</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <THead><Tr><Th>Nom</Th><Th>Effet</Th><Th>Fin</Th><Th>Vérifié</Th><Th>Source</Th></Tr></THead>
                  <TBody>
                    {(params ?? []).map((p: any) => (
                      <Tr key={p.id}>
                        <Td>{p.name}</Td>
                        <Td>{p.effective_from}</Td>
                        <Td>{p.effective_to ?? "—"}</Td>
                        <Td><Badge variant={p.verified ? "success" : "danger"}>{p.verified ? "Vérifié" : "Non vérifié"}</Badge></Td>
                        <Td className="max-w-[300px] truncate text-xs text-muted-foreground">{p.source_reference ?? "—"}</Td>
                      </Tr>
                    ))}
                  </TBody>
                </Table>
              </CardContent>
            </Card>
          ),
        },
      ]} />

      <Modal ouvert={nouveau} titre="Nouveau lot de paie" onFermer={() => setNouveau(false)}>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="mois">Mois (1-12)</Label>
              <Input id="mois" type="number" min="1" max="12" value={mois} onChange={(e) => setMois(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="annee">Année</Label>
              <Input id="annee" type="number" min="2020" value={annee} onChange={(e) => setAnnee(e.target.value)} />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setNouveau(false)}>Annuler</Button>
            <Button onClick={() => creerRun.mutate()} disabled={!mois || !annee || creerRun.isPending}>Créer</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
