import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, notifierErreur } from "@/lib/api";
import { ResourcePage } from "@/components/ResourcePage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { CheckCircle2 } from "lucide-react";

const STATUTS: Record<string, any> = {
  recue: "muted", a_valider: "warning", validee: "success", partielle: "warning",
  payee: "success", en_retard: "danger", litige: "danger",
};

export default function FacturesFournisseursPage() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["invoicing/supplier-invoices/"] });
  const valider = useMutation<any, unknown, number>({
    mutationFn: (id: number) => api.post(`invoicing/supplier-invoices/${id}/valider/`, {}),
    onSuccess: () => { toast.success("Facture validée humainement — le fournisseur n'est débité qu'après validation."); refresh(); },
    onError: notifierErreur,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Factures fournisseurs</h1>
      <p className="text-sm text-muted-foreground">
        Aucune facture fournisseur ne sort de « à valider » sans décision humaine explicite.
      </p>
      <ResourcePage
        titre="Factures fournisseurs"
        endpoint="invoicing/supplier-invoices/"
        colonnes={[
          { key: "supplier_reference", label: "Réf." },
          { key: "supplier_name", label: "Fournisseur" },
          { key: "invoice_date", label: "Facturée le" },
          { key: "due_date", label: "Échéance" },
          { key: "total_ttc", label: "TTC" },
          { key: "status", label: "Statut", render: (f: any) => <Badge variant={STATUTS[f.status] ?? "muted"}>{f.status_label ?? f.status}</Badge> },
        ]}
        champs={[
          { name: "supplier", label: "Fournisseur", type: "select", optionsUrl: "invoicing/suppliers/", required: true },
          { name: "supplier_reference", label: "Référence fournisseur" },
          { name: "invoice_date", label: "Date de facture", type: "date", required: true },
          { name: "received_date", label: "Date de réception", type: "date" },
          { name: "due_date", label: "Échéance", type: "date" },
          { name: "expense_account", label: "Compte de charge" },
        ]}
        actions={(f: any) => f.status === "a_valider" ? (
          <Button size="icon" variant="ghost" title="Valider"
            onClick={() => { if (window.confirm("Valider cette facture fournisseur ?")) valider.mutate(f.id); }}>
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          </Button>
        ) : null}
      />
    </div>
  );
}
