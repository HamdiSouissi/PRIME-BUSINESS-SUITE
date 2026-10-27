# Prime Business Suite

Suite de gestion d'entreprise française — RH, paie, facturation, comptabilité, trésorerie,
budgets, dividendes, conformité, contrats, assistant IA interne (optionnel).

**Stack** : Django 5.1 / DRF / PostgreSQL (SQLite en dev) · React 18 / TypeScript / Vite / Tailwind · Celery + Redis · Docker.

---

## Démarrage rapide (développement, sans Docker)

Prérequis : Python 3.11+, Node 22+.

```bash
# Backend
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py seed_demo      # données de démonstration (dev uniquement)
../.venv/bin/python manage.py runserver 0.0.0.0:8000

# Frontend (autre terminal)
cd ../frontend
npm ci
npm run dev                                  # http://localhost:5173
```

Compte de démonstration : `admin@primevision.example` / `PrimeBDD-2026!` (à changer immédiatement, dev uniquement).

## Démarrage Docker (production-like)

```bash
docker compose up --build
# Frontend : http://localhost:8080 · API : http://localhost:8000/api/
```

⚠️ Les fichiers Docker ont été validés statiquement (pas de Docker dans l'environnement de développement
utilisé) : avant mise en production, suivre la checklist de `docs/deploiement.md`.

## Tests

```bash
cd backend && ../.venv/bin/python -m pytest      # 68 tests passent, 2 ignorés (backup fichier, hors mémoire)
cd frontend && npm test                          # 5 tests Vitest
```

## Documentation

| Document | Contenu |
|---|---|
| `docs/demarrage.md` | Installation pas à pas, comptes, données de démo |
| `docs/deploiement.md` | Docker de A à Z, Windows Docker Desktop, variables d'environnement |
| `docs/securite.md` | Authentification, RBAC, audit, chiffrement des clés IA, sauvegardes |
| `docs/regles-de-paie.md` | Fonctionnement du moteur de règles versionnées, sources, blocages |
| `docs/limites.md` | Ce qui est **conçu et préparé** vs **validé/certifié** — lecture obligatoire |

## Limites assumées (résumé — détail dans `docs/limites.md`)

- **Paie** : moteur de règles versionnées avec dates d'effet et sources officielles documentées ;
  chaque jeu de paramètres doit être marqué « vérifié » avant validation définitive. Aucun taux codé en dur.
- **DSN** : génération d'un fichier structuré et archivage, étiqueté **« non transmis, non accusé, non certifié »**.
  Aucune transmission à net-entreprises n'est implémentée.
- **Facture électronique** : l'export d'un PDF lisible n'est **pas** de la facturation électronique au sens de la
  réforme 2026 ; l'intégration d'une plateforme de dématérialisation partenaire est préparée mais non réalisée.
- **Export comptable** : format « préparé pour expert-comptable » (structure FEC-like), **non certifié FEC** —
  votre expert-comptable valide.
- **Trésorerie** : aucun mouvement bancaire réel — préparation de fichiers et simulation uniquement.
- **IA** : désactivée par défaut ; clé API chiffrée côté serveur, jamais exposée au navigateur ni aux logs ;
  l'utilisateur contrôle toujours la décision finale (paie, virements, dividendes, déclarations exclus).
- **Conformité/RGPD** : centre d'alertes **configuré par vos soins** — les alertes ne prétendent pas couvrir
  l'universalité des obligations légales applicables à votre cas.

## État du dépôt

Conçu et vérifié dans l'environnement de développement : démarrage local (SQLite), migrations sur base vierge,
tests automatisés (68 + 5), build frontend. Publication Git : voir le statut en fin du rapport de livraison.

---

## Arborescence

```
backend/           API Django (apps/<module>/ par domaine)
frontend/          SPA React/TS (src/pages, src/components/ui)
docker/            Dockerfiles + nginx.conf
scripts/           backup_sqlite.sh (et backup_pg.sh pour PostgreSQL)
docs/              Documentation en français
docker-compose.yml Pile complète
```
