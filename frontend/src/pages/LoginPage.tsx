import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";

export default function LoginPage() {
  const { connexion, chargement } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function soumettre(e: React.FormEvent) {
    e.preventDefault();
    try {
      await connexion(email, password);
      navigate("/");
    } catch {
      /* erreur notifiée via toast dans api.ts */
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-center">
            <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-xl font-bold text-primary-foreground">
              P
            </div>
            Prime Business Suite
          </CardTitle>
          <p className="text-center text-sm text-muted-foreground">Connectez-vous à votre espace</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={soumettre} className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="email">Adresse email</Label>
              <Input id="email" type="email" autoComplete="username" required value={email}
                     onChange={(e) => setEmail(e.target.value)} placeholder="vous@entreprise.fr" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Mot de passe</Label>
              <Input id="password" type="password" autoComplete="current-password" required value={password}
                     onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
            </div>
            <Button type="submit" className="w-full" disabled={chargement}>
              {chargement ? "Connexion…" : "Se connecter"}
            </Button>
          </form>
          <p className="mt-4 text-center text-xs text-muted-foreground">
            Données hébergées — l'assistant IA est désactivé par défaut.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
