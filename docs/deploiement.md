# Déploiement — Docker de A à Z

> ⚠️ **Transparence** : ces fichiers Docker ont été écrits et relus mais **non exécutés** dans
> l'environnement de développement (sandbox sans Docker). Avant production, parcourez la
> checklist de validation en bas de ce document sur une machine avec Docker Desktop.

## 1. Prérequis

- **Windows** : Docker Desktop avec moteur Linux (WSL 2 activé), partage du lecteur du dépôt autorisé.
- **macOS/Linux** : Docker Engine récent + plugin compose v2 (`docker compose version`).

## 2. Configuration

Créer un fichier `.env` à la racine à partir du modèle (jamais commité — il est dans `.gitignore`) :

```bash
cp .env.example .env
```

```env
SECRET_KEY=generez-une-longue-chaine-aleatoire
POSTGRES_DB=pbs
POSTGRES_USER=pbs
POSTGRES_PASSWORD=mot-de-passe-fort
FIELD_ENCRYPTION_KEY=    # voir §5 : clé de chiffrement des clés API (Fernet, 44 caractères base64)
ALLOWED_HOSTS=localhost,127.0.0.1,frontend
CORS_ALLOWED_ORIGINS=http://localhost:8080
```

> ⚠️ **`POSTGRES_PASSWORD` n'est pris en compte qu'à la première initialisation du volume
> `pgdata`.** Sur un volume existant, le rôle PostgreSQL conserve son mot de passe initial :
> modifier la variable produit alors `FATAL: password authentication failed for user "pbs"`
> (procédures de réparation dans `docs/demarrage.md`, § 8).
>
> Les variables `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` sont lues directement par
> `backend/config/settings.py` (les variantes préfixées `DJANGO_*` sont également acceptées).

Générer `FIELD_ENCRYPTION_KEY` :

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 3. Lancement

```bash
docker compose up --build
```

- Frontend : `http://localhost:8080`
- API : `http://localhost:8000/api/` · Admin Django : `http://localhost:8000/admin/`
- Le backend applique `migrate` automatiquement au démarrage.
- **Premier lancement** : aucun compte n'existe → créez-le (sinon *401 Unauthorized* au login) :
  `docker compose exec backend python manage.py seed_demo`
  (ou `DEMO_SEED=1` dans `.env` avant `up`, ou `createsuperuser` pour un vrai compte).

## 4. Architecture des services

| Service | Image | Rôle |
|---|---|---|
| `db` | `postgres:16.4-alpine` | Base de données (volume persistant `pgdata`) |
| `redis` | `redis:7.4-alpine` | Broker Celery + cache |
| `backend` | `docker/Dockerfile.backend` | API Django/Wsgi (gunicorn, 3 workers, user non-root) |
| `worker` | même image | Tâches Celery (paie mensuelle, rappels, conformité) |
| `frontend` | `docker/Dockerfile.frontend` | Build Vite puis Nginx, proxy `/api/` et `/admin/` vers `backend` |

L'image backend installe **Pango/Cairo** : les PDF (bulletins de paie, factures) passent alors par
WeasyPrint (HTML/CSS complet). Sans ces bibliothèques système, l'application bascule automatiquement
sur un rendu ReportLab simplifié (c'est le cas dans le sandbox de développement).

## 5. Secrets et sécurité

- Aucun secret dans le dépôt ; tout passe par variables d'environnement.
- `SECRET_KEY` : obligatoire en production (le compose refuse un défaut silencieux : définissez-la dans `.env`).
- Clés d'API IA : saisies côté interface, chiffrées avec `FIELD_ENCRYPTION_KEY` avant stockage.
- Le conteneur backend tourne avec l'utilisateur `pbs` (non-root).
- **TLS / redirection HTTPS** : `SECURE_SSL_REDIRECT` vaut `0` dans la stack Docker
  locale (nginx en HTTP pur). En production derrière un reverse proxy TLS, passer
  `SECURE_SSL_REDIRECT=1` : le proxy doit transmettre `X-Forwarded-Proto: https`
  (déjà fait par le nginx du dépôt), et `settings.py` fait confiance à cet en-tête
  via `SECURE_PROXY_SSL_HEADER` — pas de boucle de redirection.
- Le conteneur backend déclare un `HEALTHCHECK` sur `/api/health/` et le service
  `frontend` n'attend plus que le backend soit `healthy` pour démarrer.

## 6. Sauvegardes PostgreSQL

```bash
# Sauvegarde
docker compose exec db pg_dump -U pbs -Fc pbs > backups/pbs-$(date +%F%H%M).dump
# Restauration (service backend arrêté)
docker compose stop backend worker
cat backups/pbs-XXXX.dump | docker compose exec -T db pg_restore -U pbs -d pbs --clean --if-exists
docker compose start backend worker
```

Mettre en place une tâche planifiée (cron / planificateur Windows) sur l'hôte. Tester la restauration
au moins une fois — voir la procédure automatisée pendant le dev dans `tests/test_backup_restore.py`.

## 7. Checklist de première validation (sur machine Docker)

1. `docker compose config` — le fichier est syntaxiquement valide.
2. `docker compose build` — les deux images se construisent sans erreur.
3. `docker compose up` — `db` et `redis` passent *healthy*, `backend` migre puis écoute sur 8000.
4. `curl http://localhost:8000/api/health/` → `{"status":"ok"}`.
5. `http://localhost:8080` affiche l'écran de connexion ; se connecter avec le compte démo.
6. Générer un bulletin PDF (Paie) et une facture PDF : vérifier le rendu (WeasyPrint actif).
7. `docker compose exec backend python manage.py check --deploy` — corriger les avertissements.
8. Procédure de sauvegarde puis restauration exécutée bout en bout une fois.

## 8. Mise à jour

```bash
git pull
docker compose up --build -d        # reconstruit et applique les migrations au démarrage
```
