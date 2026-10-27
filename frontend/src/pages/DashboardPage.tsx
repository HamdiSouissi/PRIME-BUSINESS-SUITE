import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alerte } from "@/components/ui/modal";
import { fmtEuro } from "@/lib/utils";
import { Link } from "react-router-dom";

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get("dashboard/")).data,
  });

  if (isLoading) return <p className="text-muted-foreground">Chargement…</p>;
  if (!data) return <p className="text-muted-foreground">Aucune donnée.</p>;

  const tuiles = [
    { label: "Solde bancaire disponible", valeur: data.tresorerie?.solde_bancaire_disponible, url: "/tresorerie",
      note: data.tresorerie?.definition },
    { label: "Encours clients (TTC)", valeur: data.facturation?.encours_clients_ttc, url: "/factures" },
    { label: "MRR (HT)", valeur: data.abonnements?.mrr_ht, url: "/abonnements" },
    { label: "CA du mois (HT, factures émises)", valeur: data.chiffre_affaires_mois, url: "/factures" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Tableau de bord {data.entreprise ? `— ${data.entreprise.nom}` : ""}</h1>
        <p className="text-sm text-muted-foreground">Chaque carte indique sa définition de calcul.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {tuiles.map((t) => (
          <Link key={t.label} to={t.url}>
            <Card className="h-full transition-shadow hover:shadow-md">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{t.label}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">
                  {t.valeur === null || t.valeur === undefined ? "—" : fmtEuro(t.valeur)}
                </p>
                {t.note ? <p className="mt-1 text-xs text-muted-foreground">{t.note}</p> : null}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-base">À traiter</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p><span className="font-medium">{data.rh?.absences_en_attente ?? 0}</span> demande(s) d'absence en attente — <Link className="underline" to="/absences">voir</Link></p>
            <p><span className="font-medium">{data.rh?.frais_en_attente ?? 0}</span> note(s) de frais soumise(s) — <Link className="underline" to="/depenses">voir</Link></p>
            <p><span className="font-medium">{data.facturation?.factures_echues ?? 0}</span> facture(s) échue(s)
              {data.facturation?.montant_echu_ttc ? ` (${fmtEuro(data.facturation.montant_echu_ttc)})` : ""} — <Link className="underline" to="/factures">relancer</Link></p>
            <p><span className="font-medium">{data.conformite?.depassees ?? 0}</span> obligation(s) dépassée(s) — <Link className="underline" to="/conformite">traiter</Link></p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Conformité</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm">Obligations à faire : <span className="font-medium">{data.conformite?.a_faire ?? 0}</span> · dépassées : <span className="font-medium">{data.conformite?.depassees ?? 0}</span></p>
            <Alerte variante="info">
              Ces alertes reposent sur votre propre configuration d'échéances. Elles ne prétendent pas couvrir
              l'ensemble des obligations légales applicables à votre situation.
            </Alerte>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
