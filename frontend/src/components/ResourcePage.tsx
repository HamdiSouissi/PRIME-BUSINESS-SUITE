import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Search, RefreshCw } from "lucide-react";
import { api, notifierErreur } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { TBody, THead, Table, Td, Th, Tr } from "@/components/ui/table";
import { toast } from "sonner";

export interface ChampForm {
  name: string;
  label: string;
  type?: "text" | "email" | "number" | "date" | "textarea" | "select" | "password";
  required?: boolean;
  options?: { value: string; label: string }[];
  optionsUrl?: string; // charge options depuis l'API (id|name)
  placeholder?: string;
  step?: string;
  hideOnEdit?: boolean;
  min?: string;
}

export interface Colonne<T> {
  key: string;
  label: string;
  render?: (item: T) => ReactNode;
  className?: string;
}

interface ResourcePageProps<T extends { id: number }> {
  titre: string;
  description?: string;
  endpoint: string;
  colonnes: Colonne<T>[];
  champs: ChampForm[];
  peutCreer?: boolean;
  peutModifier?: boolean;
  peutSupprimer?: boolean;
  filtres?: Record<string, string>;
  actions?: (item: T, refresh: () => void) => ReactNode;
  formulaireInitial?: Record<string, unknown>;
  onRowClick?: (item: T) => void;
}

function useOptions(url?: string) {
  const { data } = useQuery({
    queryKey: ["options", url],
    queryFn: async () => {
      if (!url) return [];
      const res = await api.get(url, { params: { page_size: 500 } });
      const payload = res.data;
      const rows = Array.isArray(payload) ? payload : payload.results ?? [];
      return rows.map((r: any) => ({
        value: String(r.id),
        label: r.name || r.full_name || r.label || r.email || r.code || `#${r.id}`,
      }));
    },
    enabled: Boolean(url),
  });
  return data ?? [];
}

function Champ({ champ, valeur, onChange }: { champ: ChampForm; valeur: string; onChange: (v: string) => void }) {
  const options = useOptions(champ.optionsUrl);
  const type = champ.type ?? "text";
  const communs = {
    id: champ.name,
    required: champ.required,
    placeholder: champ.placeholder,
  };
  return (
    <div className="space-y-1">
      <Label htmlFor={champ.name}>{champ.label}{champ.required ? " *" : ""}</Label>
      {type === "textarea" ? (
        <Textarea {...communs} value={valeur} onChange={(e) => onChange(e.target.value)} />
      ) : type === "select" ? (
        <Select {...communs} value={valeur} onChange={(e) => onChange(e.target.value)}>
          <option value="">— Choisir —</option>
          {(champ.options ?? options).map((o: { value: string; label: string }) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </Select>
      ) : (
        <Input
          {...communs}
          type={type}
          step={champ.step}
          min={champ.min}
          value={valeur}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </div>
  );
}

export function ResourcePage<T extends { id: number }>(props: ResourcePageProps<T>) {
  const qc = useQueryClient();
  const [recherche, setRecherche] = useState("");
  const [rechercheDebounced, setRechercheDebounced] = useState("");
  const [modalOuverte, setModalOuverte] = useState(false);
  const [edition, setEdition] = useState<T | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});

  useEffect(() => {
    const t = setTimeout(() => setRechercheDebounced(recherche), 300);
    return () => clearTimeout(t);
  }, [recherche]);

  const refresh = () => qc.invalidateQueries({ queryKey: [props.endpoint] });

  const { data, isLoading, error } = useQuery({
    queryKey: [props.endpoint, rechercheDebounced, props.filtres],
    queryFn: async () => {
      const res = await api.get(props.endpoint, {
        params: { search: rechercheDebounced || undefined, ...(props.filtres ?? {}) },
      });
      return Array.isArray(res.data) ? { results: res.data } : res.data;
    },
  });

  const supprimer = useMutation<any, unknown, number>({
    mutationFn: (id: number) => api.delete(`${props.endpoint}${id}/`),
    onSuccess: () => {
      toast.success("Supprimé.");
      refresh();
    },
    onError: notifierErreur,
  });

  const enregistrer = useMutation<any, unknown, Record<string, unknown>>({
    mutationFn: (payload: Record<string, unknown>) =>
      edition
        ? api.patch(`${props.endpoint}${edition.id}/`, payload)
        : api.post(props.endpoint, payload),
    onSuccess: () => {
      toast.success(edition ? "Modifié." : "Créé.");
      setModalOuverte(false);
      setEdition(null);
      refresh();
    },
    onError: notifierErreur,
  });

  const colonnes = props.colonnes;
  const lignes: T[] = data?.results ?? [];

  function ouvrirCreation() {
    setEdition(null);
    const init: Record<string, string> = {};
    props.champs.forEach((c) => {
      const defaut = props.formulaireInitial?.[c.name];
      init[c.name] = defaut === undefined ? "" : String(defaut);
    });
    setForm(init);
    setModalOuverte(true);
  }

  function ouvrirEdition(item: T) {
    setEdition(item);
    const init: Record<string, string> = {};
    props.champs.forEach((c) => {
      const v = (item as Record<string, unknown>)[c.name];
      init[c.name] = v === null || v === undefined ? "" : String(v);
    });
    setForm(init);
    setModalOuverte(true);
  }

  function soumettre(e: React.FormEvent) {
    e.preventDefault();
    const payload: Record<string, unknown> = {};
    props.champs.forEach((c) => {
      if (edition && c.hideOnEdit) return;
      const v = form[c.name];
      if (v === "" || v === undefined) return;
      payload[c.name] = c.type === "select" && !/^\d+$/.test(v) ? v : v;
    });
    enregistrer.mutate(payload);
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle>{props.titre}</CardTitle>
          {props.description && <p className="mt-1 text-sm text-muted-foreground">{props.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              className="w-64 pl-8"
              placeholder="Rechercher…"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
            />
          </div>
          <Button variant="outline" size="icon" onClick={refresh} aria-label="Rafraîchir">
            <RefreshCw className="h-4 w-4" />
          </Button>
          {props.peutCreer !== false && (
            <Button onClick={ouvrirCreation}>
              <Plus className="h-4 w-4" /> Nouveau
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="py-8 text-center text-sm text-destructive">Erreur de chargement.</p>
        ) : isLoading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">Chargement…</p>
        ) : !lignes.length ? (
          <p className="py-8 text-center text-sm text-muted-foreground">Aucun élément.</p>
        ) : (
          <Table>
            <THead>
              <Tr>
                {colonnes.map((c) => (
                  <Th key={c.key} className={c.className}>{c.label}</Th>
                ))}
                <Th className="w-32 text-right">Actions</Th>
              </Tr>
            </THead>
            <TBody>
              {lignes.map((item) => (
                <Tr key={item.id} className={props.onRowClick ? "cursor-pointer" : ""}
                    onClick={props.onRowClick ? () => props.onRowClick!(item) : undefined}>
                  {colonnes.map((c) => (
                    <Td key={c.key} className={c.className}>
                      {c.render ? c.render(item) : String((item as Record<string, unknown>)[c.key] ?? "—")}
                    </Td>
                  ))}
                  <Td className="text-right" onClick={(e) => e.stopPropagation()}>
                    <div className="flex justify-end gap-1">
                      {props.actions?.(item, refresh)}
                      {props.peutModifier !== false && (
                        <Button variant="ghost" size="icon" onClick={() => ouvrirEdition(item)} aria-label="Modifier">
                          <Pencil className="h-4 w-4" />
                        </Button>
                      )}
                      {props.peutSupprimer !== false && (
                        <Button
                          variant="ghost" size="icon" aria-label="Supprimer"
                          onClick={() => {
                            if (window.confirm("Confirmer la suppression ?")) supprimer.mutate(item.id);
                          }}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </div>
                  </Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        )}
      </CardContent>

      <Modal
        ouvert={modalOuverte}
        titre={edition ? `Modifier ${props.titre.toLowerCase()}` : `Créer — ${props.titre}`}
        onFermer={() => setModalOuverte(false)}
        large
      >
        <form onSubmit={soumettre} className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {props.champs
            .filter((c) => !(edition && c.hideOnEdit))
            .map((champ) => (
              <Champ
                key={champ.name}
                champ={champ}
                valeur={form[champ.name] ?? ""}
                onChange={(v) => setForm((f) => ({ ...f, [champ.name]: v }))}
              />
            ))}
          <div className="col-span-full flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => setModalOuverte(false)}>Annuler</Button>
            <Button type="submit" disabled={enregistrer.isPending}>
              {enregistrer.isPending ? "Enregistrement…" : edition ? "Enregistrer" : "Créer"}
            </Button>
          </div>
        </form>
      </Modal>
    </Card>
  );
}
