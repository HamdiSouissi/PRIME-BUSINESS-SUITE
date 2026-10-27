import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { FileText, RotateCcw, SendHorizontal, Bell, Download } from "lucide-react";

const STATUTS: Record<string, any> = {
  brouillon: "muted", emise: "info", partiellement_payee: "warning", payee: "success",
  en_retard: "danger", annulee_par_avoir: "muted",
};

export default function FacturesPage() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["invoicing/invoices/"] });

  const agir = useMutation<any, unknown, { id: number; act: string }>({
    mutationFn: ({ id, act }: { id: number; act: string }) =>
      api.post(`invoicing/invoices/${id}/${act}/`, {}),
    onSuccess: (_d, v) => {
      toast.success(v.act === "avoir" ? "Avoir créé — la facture d'origine reste inchangée (comptabilité par contre-passation)."
        : v.act === "relance" ? "Relance enregistrée (doublons évités par niveau/délai)." : "Statut mis à jour.");
      refresh();
    },
    onError: notifierErreur,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Factures clients</h1>
      <p className="text-sm text-muted-foreground">
        Toute facture émise est <strong>immuable</strong> : les corrections passent obligatoirement par avoir
        (contre-passation). Numérotation séquentielle anti-trou, montants HT/TVA/TTC recalculés.
      </p>
      <ResourcePage
        titre="Factures"
        endpoint="invoicing/invoices/"
        colonnes={[
          { key: "number", label: "N°" },
          { key: "client_name", label: "Client" },
          { key: "issue_date", label: "Émise le" },
          { key: "due_date", label: "Échéance" },
          { key: "total_ttc", label: "TTC" },
          { key: "reste_a_payer", label: "Reste" },
          { key: "status", label: "Statut", render: (f: any) => <Badge variant={STATUTS[f.status] ?? "muted"}>{f.status}</Badge> },
        ]}
        champs={[
          { name: "client", label: "Client", type: "select", optionsUrl: "invoicing/clients/", required: true },
          { name: "issue_date", label: "Date d'émission", type: "date", required: true },
          { name: "due_date", label: "Échéance", type: "date" },
          { name: "notes", label: "Notes", type: "textarea" },
        ]}
        actions={(f: any) => (
          <>
            {f.status === "brouillon" && (
              <Button size="icon" variant="ghost" title="Émettre (devient définitive)"
                onClick={() => agir.mutate({ id: f.id, act: "emettre" })}>
                <FileText className="h-4 w-4" />
              </Button>
            )}
            {["emise", "partiellement_payee", "en_retard"].includes(f.status) && (
              <>
                <Button size="icon" variant="ghost" title="Relancer"
                  onClick={() => agir.mutate({ id: f.id, act: "relance" })}>
                  <Bell className="h-4 w-4" />
                </Button>
                <Button size="icon" variant="ghost" title="Émettre un avoir"
                  onClick={() => {
                    if (window.confirm("Créer un avoir qui annule intégralement cette facture ?"))
                      agir.mutate({ id: f.id, act: "avoir" });
                  }}>
                  <RotateCcw className="h-4 w-4 text-destructive" />
                </Button>
              </>
            )}
            {f.status !== "brouillon" && (
              <Button size="icon" variant="ghost" title="Télécharger le PDF"
                onClick={async () => {
                  try {
                    const res = await api.get(`invoicing/invoices/${f.id}/telecharger/`, { responseType: "blob" });
                    const url = URL.createObjectURL(res.data as Blob);
                    const a = document.createElement("a");
                    a.href = url; a.download = `facture-${f.number}.pdf`; a.click();
                    URL.revokeObjectURL(url);
                  } catch (e) { notifierErreur(e, "PDF indisponible."); }
                  // notifierErreur accepte un message de secours en 2e argument
                }}>
                <Download className="h-4 w-4" />
              </Button>
            )}
          </>
        )}
      />
      <p className="text-xs text-muted-foreground">
        PDF : lisible et archivé ; il ne vaut pas “facture électronique” au sens de la réforme 2026 (plateforme agréée requise).
      </p>
    </div>
  );
}
