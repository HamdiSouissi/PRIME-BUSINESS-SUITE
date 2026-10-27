import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { TBody, THead, Table, Td, Th, Tr } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

const METHODES: Record<string, any> = { POST: "info", PATCH: "warning", PUT: "warning", DELETE: "danger" };

export default function AuditPage() {
  const [chemin, setChemin] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["audit", chemin],
    queryFn: async () => {
      const res = await api.get("audit/", { params: { path: chemin || undefined, page_size: 100 } });
      const d = res.data;
      return Array.isArray(d) ? d : d.results ?? [];
    },
  });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Journal d'audit</h1>
      <p className="text-sm text-muted-foreground">
        Enregistrements immuables de toutes les actions d'écriture (POST/PUT/PATCH/DELETE) : qui, quoi, quand, sur quel chemin.
      </p>
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Dernières actions</CardTitle>
          <div className="w-72 space-y-1">
            <Label htmlFor="filtre" className="sr-only">Filtrer par chemin</Label>
            <Input id="filtre" placeholder="Filtrer par chemin (ex. invoicing)" value={chemin} onChange={(e) => setChemin(e.target.value)} />
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? <p className="text-sm text-muted-foreground">Chargement…</p> : (
            <Table>
              <THead><Tr><Th>Date</Th><Th>Utilisateur</Th><Th>Méthode</Th><Th>Chemin</Th><Th>Code</Th></Tr></THead>
              <TBody>
                {(data ?? []).map((l: any) => (
                  <Tr key={l.id}>
                    <Td className="whitespace-nowrap text-xs">{l.created_at ? new Date(l.created_at).toLocaleString("fr-FR") : "—"}</Td>
                    <Td className="text-xs">{l.user_email ?? "—"}</Td>
                    <Td><Badge variant={METHODES[l.method] ?? "muted"}>{l.method}</Badge></Td>
                    <Td className="font-mono text-xs">{l.path}</Td>
                    <Td className="text-xs">{l.status_code}</Td>
                  </Tr>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
