import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Onglet {
  id: string;
  label: string;
  contenu: ReactNode;
}

export function Tabs({ onglets, defaultId }: { onglets: Onglet[]; defaultId?: string }) {
  const [actif, setActif] = useState(defaultId ?? onglets[0]?.id);
  const courant = onglets.find((o) => o.id === actif) ?? onglets[0];
  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-1 rounded-lg bg-muted p-1">
        {onglets.map((o) => (
          <button
            key={o.id}
            onClick={() => setActif(o.id)}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              actif === o.id ? "bg-card shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
      {courant ? courant.contenu : null}
    </div>
  );
}
