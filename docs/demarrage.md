# Démarrage — guide pas à pas

## 0. Erreur fréquente : `401 Unauthorized` à la connexion

Un **401 sur `/api/auth/login/`** signifie simplement : *« identifiants inexistants ou
incorrects »*. Sur une base neuve (ex. premier `docker compose up`), **aucun compte n'existe
encore**. Il faut en créer un :

```bash
# Docker — une seule fois, après le 1er démarrage :
docker compose exec backend python manage.py seed_demo
# puis connectez-vous avec admin@primevision.example / PrimeBDD-2026!

# Ou créer votre propre compte administrateur :
docker compose exec backend python manage.py createsuperuser

# Astuce dev : DEMO_SEED=1 dans .env fait l'amorçage automatiquement au démarrage.
```

⚠️ Les erreurs `Attempting to use a disconnected port object` / `background.js`
viennent d'une **extension de votre navigateur** (gestionnaire de mots de passe, etc.) —
elles ne proviennent pas de l'application et n'ont aucun effet sur elle.

## 1. Prérequis

- Python 3.11 ou plus (`python3 --version`)
- Node.js 22 (`node --version`)
- Optionnel mais recommandé hors dev : Docker Desktop (Windows/macOS) ou Docker Engine (Linux)

## 2. Backend (API)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows : .venv\\Scripts\\activate
pip install -r backend/requirements.txt
cd backend
python manage.py migrate
python manage.py seed_demo       # facultatif : données de démonstration
python manage.py runserver 0.0.0.0:8000
```

Vérification : `curl http://localhost:8000/api/health/` → `{"status":"ok","database":true}`.

### Base de données

Par défaut : **SQLite** (`backend/db.sqlite3`, aucun serveur requis — adapté au développement).
Pour PostgreSQL, définir `DATABASE_URL=postgres://user:mdp@hote:5432/base` (voir `.env.example`
à la racine du dépôt).

## 3. Frontend (SPA)

```bash
cd frontend
npm ci           # installation reproductible (package-lock.json fourni)
npm run dev      # http://localhost:5173 — l'API /api est proxifiée vers le port 8000
```

Build de production : `npm run build` (vérifie TypeScript puis bundle Vite).

## 4. Comptes de démonstration (créés par `seed_demo`)

| Compte | Rôle | Mot de passe |
|---|---|---|
| `admin@primevision.example` | Administrateur | `PrimeBDD-2026!` |

⚠️ Exclusivement pour le dev/démo. Changez ces identifiants avant toute exposition.

Le jeu de démo comprend : entreprise « Prime Vision Solutions », plan comptable par défaut,
salariés et contrats d'exemple, clients/fournisseurs, compte bancaire, catalogue de conformité,
fournisseur IA « Ollama local » (désactivé tant qu'Ollama n'est pas installé).

## 5. Assistant IA (optionnel — désactivé par défaut)

L'ensemble de l'application fonctionne **sans IA**. Pour l'activer :

- **Ollama (défaut, local)** : installer Ollama sur le serveur (`https://ollama.com`), télécharger un modèle,
  puis dans *Assistant IA → Fournisseurs*, créer un fournisseur de type `ollama`, URL `http://localhost:11434`,
  renseigner le modèle choisi (aucun identifiant de modèle n'est codé en dur dans l'application).
- **CodeCraftAPI** : fournisseur de type `codecraft`, base `https://codecraftapi.com/v1`
  (endpoints `GET /models` et `POST /chat/completions`), clé renseignée dans le champ dédié —
  elle est **chiffrée côté serveur** et n'est jamais renvoyée au navigateur ni écrite dans les logs.

## 6. Widget Celery (tâches planifiées, optionnel en dev)

En développement, les tâches tournent de manière synchrone (`CELERY_TASK_ALWAYS_EAGER=1` par défaut).
En production : services `worker` et `redis` du `docker-compose.yml`.

## 7. Sauvegarde / restauration (dev SQLite)

```bash
scripts/backup_sqlite.sh backend/db.sqlite3 backups/$(date +%F).sqlite3
# Restauration : arrêter le serveur, remplacer backend/db.sqlite3 par la copie, redémarrer.
```

Production : `scripts/backup_pg.sh` (pg_dump) — procédure détaillée dans `docs/deploiement.md`.
La procédure de restauration est décrite et le test automatisé correspondant est dans `backend/tests/test_backup_restore.py`.

## 8. Dépannage Docker

### `FATAL: password authentication failed for user "pbs"` (suivi d'un 502 sur `/api/`)

Symptômes dans les logs : la base démarre (« Skipping initialization »), puis
`FATAL: password authentication failed for user "pbs"`, le conteneur `backend`
s'arrête sur `python manage.py migrate`, et nginx renvoie
`502 Bad Gateway` / `connect() failed (113: Host is unreachable)`.

Cause : **`POSTGRES_PASSWORD` n'est appliqué que lors de la première initialisation
du volume `pgdata`**. Si le volume existe déjà (créé avec un autre mot de passe, ou
avant l'ajout du fichier `.env`), le rôle PostgreSQL garde son ancien mot de passe.
Le `healthcheck` du service `db` échoue alors lors d'une authentification réelle, ce
qui rend le problème visible dans `docker compose ps`.

Deux solutions :

**Option A — conserver les données** (réaligner le mot de passe du rôle sur `.env`) :

```bash
# La socket locale du conteneur fait confiance à POSTGRES_USER, même avec l'auth TCP cassée
docker compose exec db psql -U pbs -d pbs -c "ALTER ROLE pbs PASSWORD 'admin123!';"
docker compose up -d   # le backend redémarre, les migrations passent
```

(Remplacer `admin123!` par la valeur de `POSTGRES_PASSWORD` de votre `.env`.)

**Option B — repartir sur une base neuve** (données locales perdues, acceptable en démo) :

```bash
docker compose down -v          # supprime le volume pgdata
docker compose up --build -d
# puis recréer le compte de démonstration :
docker compose exec backend python manage.py seed_demo
# (ou mettre DEMO_SEED=1 dans .env avant `up`)
```

### La page s'affiche sans aucun style (texte brut, formulaire non mis en forme)

Le plugin Tailwind n'était pas enregistré dans `frontend/vite.config.ts` : le CSS
livré ne contenait aucune classe utilitaire. Ce bogue est corrigé dans le dépôt.
Après un `git pull`, reconstruire l'image frontend (sans cache) puis recharger
le navigateur avec `Ctrl + Maj + R` :

```bash
docker compose build --no-cache frontend
docker compose up -d
```

### `502 Bad Gateway` sur l'API ou `/api/auth/me/`

- Un `401` sur `/api/auth/me/` est **normal** tant qu'aucune session n'est ouverte.
- Un `502` signifie que le conteneur `backend` est arrêté : diagnostiquer avec
  `docker compose logs backend` (le plus souvent l'erreur d'authentification PostgreSQL
  ci-dessus). Grâce à `restart: unless-stopped`, le service repart automatiquement
  une fois la cause corrigée.
