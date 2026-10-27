import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Tabs } from "@/components/ui/tabs";
import { fmtEuro } from "@/lib/utils";
import { useState } from "react";
import { toast } from "sonner";

function MonAbsence() {
  const qc = useQueryClient();
  const { profil } = useAuth();
  const [form, setForm] = useState({ leave_type: "", start_date: "", end_date: "", reason: "" });
  const { data: types } = useQuery({ queryKey: ["leave-types"], queryFn: async () => (await api.get("hr/leave-types/")).data });
  const liste = Array.isArray(types) ? types : types?.results ?? [];
  const soumettre = useMutation<any, unknown, void>({
    mutationFn: () => api.post("hr/leave-requests/", { ...form }),
    onSuccess: () => {
      toast.success("Demande d'absence soumise — vous serez notifié(e) de la décision.");
      setForm({ leave_type: "", start_date: "", end_date: "", reason: "" });
      qc.invalidateQueries({ queryKey: ["portail-absences"] });
    },
    onError: notifierErreur,
  });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Nouvelle demande d'absence</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1">
          <Label>Type d'absence</Label>
          <Select value={form.leave_type} onChange={(e) => setForm({ ...form, leave_type: e.target.value })}>
            <option value="">— Choisir —</option>
            {liste.map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label>Du</Label>
            <Input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
          </div>
          <div className="space-y-1">
            <Label>Au</Label>
            <Input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
          </div>
        </div>
        <div className="space-y-1">
          <Label>Motif (optionnel)</Label>
          <Input value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
        </div>
        <div className="flex justify-end">
          <Button onClick={() => soumettre.mutate()} disabled={soumettre.isPending}>Soumettre</Button>
        </div>
        <p className="text-xs text-muted-foreground">Connecté(e) en tant que {profil?.user.email}</p>
      </CardContent>
    </Card>
  );
}

function MesFrais() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ title: "", period: "" });
  const soumettre = useMutation<any, unknown, void>({
    mutationFn: () => api.post("expenses/reports/", { ...form }),
    onSuccess: () => {
      toast.success("Note de frais préparée — ajoutez des lignes puis soumettez.");
      setForm({ title: "", period: "" });
      qc.invalidateQueries({ queryKey: ["portail-frais"] });
    },
    onError: notifierErreur,
  });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Déclarer des frais</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1">
          <Label>Intitulé</Label>
          <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Déplacement client Lyon…" />
        </div>
        <div className="space-y-1">
          <Label>Période</Label>
          <Input value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} placeholder="10/2026" />
        </div>
        <div className="flex justify-end">
          <Button onClick={() => soumettre.mutate()} disabled={soumettre.isPending}>Créer la note</Button>
        </div>
      </CardContent>
    </Card>
  );
}

function MesDonnees() {
  const { profil } = useAuth();
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Mon identité</CardTitle></CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p><span className="font-medium">Email :</span> {profil?.user.email}</p>
        <p><span className="font-medium">Nom :</span> {profil?.user.first_name} {profil?.user.last_name}</p>
        <p>
          <span className="font-medium">Entreprise active :</span>{" "}
          <Badge variant="muted">{profil?.active_company_name || "—"}</Badge>
        </p>
        <p className="text-xs text-muted-foreground">
          Accès limité à vos propres données (RGPD droit d'accès) — les données d'autres salariés ne vous sont pas exposées.
        </p>
      </CardContent>
    </Card>
  );
}

export default function PortailPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Mon portail</h1>
      <p className="text-sm text-muted-foreground">
        Espace personnel du salarié : absences, frais, identité. Toutes les demandes partent en « soumise »
        en attente de validation managériale.
      </p>
      <Tabs onglets={[
        { id: "identite", label: "Mon identité", contenu: <MesDonnees /> },
        { id: "absences", label: "Demander une absence", contenu: <MonAbsence /> },
        { id: "frais", label: "Déclarer des frais", contenu: <MesFrais /> },
      ]} />
    </div>
  );
}
