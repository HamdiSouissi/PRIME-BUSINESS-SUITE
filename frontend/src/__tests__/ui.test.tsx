import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fmtEuro, cn } from "@/lib/utils";

describe("composants UI de base", () => {
  it("rend un bouton avec son libellé", () => {
    render(<Button>Enregistrer</Button>);
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeTruthy();
  });

  it("rend un badge avec variante", () => {
    render(<Badge variant="success">Valide</Badge>);
    const el = screen.getByText("Valide");
    expect(el.className).toContain("emerald");
  });

  it("fmtEuro formate en euros FR", () => {
    const s = fmtEuro(1234.5);
    expect(s).toContain("1");
    expect(s).toContain("€");
  });

  it("cn fusionne les classes", () => {
    expect(cn("a", undefined, "b")).toBe("a b");
  });

  it("fmtEuro retourne — pour null", () => {
    expect(fmtEuro(null)).toBe("—");
    expect(fmtEuro(undefined)).toBe("—");
  });
});
