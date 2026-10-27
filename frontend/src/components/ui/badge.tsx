import { type HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary/10 text-primary",
        info: "border-transparent bg-blue-100 text-blue-800",
        success: "border-transparent bg-emerald-100 text-emerald-800",
        warning: "border-transparent bg-amber-100 text-amber-800",
        danger: "border-transparent bg-red-100 text-red-800",
        muted: "border-transparent bg-muted text-muted-foreground",
        outline: "text-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

/** Choix de la variante d'un badge à partir d'un statut métier. */
export function varianteStatut(statut: string): BadgeProps["variant"] {
  const vertus = ["payee", "validee", "valide", "faite", "signe", "actif", "edite", "emise", "accepte", "remboursee", "comptabilisee", "cloture"];
  const grises = ["brouillon", "preparation", "recue", "na", "suspendu", "archive"];
  const rouges = ["refusee", "annulee", "depassee", "en_retard", "rejetee", "litige", "resilie"];
  const ambres = ["soumise", "simule", "simulation", "controle", "attente_validation", "partielle", "provisoire", "envoye", "a_valider", "en_cours", "essai", "a_faire", "decidee", "projet"];
  if (vertus.includes(statut)) return "success";
  if (grises.includes(statut)) return "muted";
  if (rouges.includes(statut)) return "danger";
  if (ambres.includes(statut)) return "warning";
  return "default";
}

export function StatutBadge({ statut, libelle }: { statut: string; libelle?: string }) {
  return <Badge variant={varianteStatut(statut)}>{libelle ?? statut}</Badge>;
}
