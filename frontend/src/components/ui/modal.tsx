import { type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ModalProps {
  ouvert: boolean;
  titre: string;
  description?: string;
  onFermer: () => void;
  children: ReactNode;
  large?: boolean;
}

export function Modal({ ouvert, titre, description, onFermer, children, large }: ModalProps) {
  if (!ouvert) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onFermer} aria-hidden />
      <div
        role="dialog"
        aria-modal
        className={cn(
          "relative z-10 max-h-[90vh] w-full overflow-y-auto rounded-lg bg-card p-5 shadow-xl",
          large ? "max-w-3xl" : "max-w-lg"
        )}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">{titre}</h2>
            {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
          </div>
          <button onClick={onFermer} className="rounded p-1 hover:bg-accent" aria-label="Fermer">
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Alerte({ variante = "info", children }: { variante?: "info" | "warn" | "warning" | "danger" | "success"; children: ReactNode }) {
  const styles = {
    info: "border-blue-300 bg-blue-50 text-blue-900",
    warn: "border-amber-300 bg-amber-50 text-amber-900",
    warning: "border-amber-300 bg-amber-50 text-amber-900",
    danger: "border-red-300 bg-red-50 text-red-900",
    success: "border-emerald-300 bg-emerald-50 text-emerald-900",
  }[variante];
  return <div className={cn("rounded-md border p-3 text-sm", styles)}>{children}</div>;
}
