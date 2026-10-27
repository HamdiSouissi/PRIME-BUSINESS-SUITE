# Sécurité

## Authentification

- Tokens JWT : accès 30 min, refresh 7 jours, rotation des refresh tokens activée.
- Mots de passe hachés avec **Argon2** (premier hasher configuré), validation de robustesse Django.
- Verrouillage de connexion : après `LOGIN_MAX_ATTEMPTS=5` échecs (par email+IP, via cache), blocage temporaire
  avec réponse HTTP 429 — configurable par variables d'environnement.
- Déconnexion côté client + révocation par rotation.

## Autorisations (RBAC)

8 rôles par défaut : `administrateur`, `direction`, `ressources_humaines`, `gestionnaire_paie`,
`comptable`, `responsable_financier`, `manager`, `salarie` (portail restreint à ses propres données).
Contrôle effectué **côté serveur** sur chaque endpoint (`HasRole`), pas seulement dans l'interface.

## Cloisonnement multi-entreprises

Chaque requête authentifiée est rattachée à une entreprise active (en-tête `X-Company-Id`, vérifiée contre
les appartenances de l'utilisateur par `CompanyMiddleware`). Les requêtes ORM filtrent par entreprise ;
un utilisateur ne voit que les données des sociétés auxquelles il appartient.

## Journal d'audit

Toutes les méthodes d'écriture (POST/PUT/PATCH/DELETE) sont journalisées avec utilisateur, chemin, code de
réponse, horodatage. Le journal est **immuable** (pas d'API de modification/suppression) et consultable par
les administrateurs via *Journal d'audit*.

## Secrets et chiffrement

- Aucun secret dans le dépôt : `SECRET_KEY`, `DATABASE_URL`, `FIELD_ENCRYPTION_KEY`, mots de passe = environnement.
- Clés API des fournisseurs IA : **chiffrées côté serveur** avant stockage, jamais renvoyées au navigateur,
  jamais écrites dans les logs (les logs d'usage IA ne conservent que métriques et statuts).
- `.env`, bases SQLite et dossiers de sauvegarde exclus de Git (`.gitignore`).

## Données personnelles (RGPD)

- Séparation stricte identité **personnelle** / **professionnelle** des salariés.
- Le *portail salarié* n'expose à l'utilisateur que **ses propres** données.
- Eléments RGPD : registre structuré à compléter par le DPO (docs), durées de conservation documentées,
  droit d'accès facilité par le portail. Voir `docs/limites.md` pour ce qui relève de votre responsabilité.

## En-têtes et transport

En production derrière un reverse proxy TLS : `SECURE_SSL_REDIRECT`, cookies `Secure`, HSTS — paramétrés
via variables d'environnement (voir `backend/env.example`). Détaillé dans `docs/deploiement.md`.

## Endpoints IA

Appels sortants uniquement côté serveur (Ollama local par défaut ; CodeCraftAPI en HTTPS).
Aucun appel IA automatique sans action utilisateur ; l'IA ne décide jamais seule d'un virement, d'une paie,
d'un dividende ou d'une déclaration.
