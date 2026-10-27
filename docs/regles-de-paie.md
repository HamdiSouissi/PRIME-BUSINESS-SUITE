# Moteur de paie — règles versionnées et sources

## Principe

Aucun taux, plafond ni barème n'est codé en dur dans le code de calcul. Tous les paramètres vivent dans la
base sous forme de **jeux de paramètres** (`payroll/parameter-sets/`) contenant des **règles de cotisation**
versionnées avec :

- **dates d'effet** (`effective_from` / `effective_to`) — la règle applicable à une paie est celle dont la
  fenêtre couvre la période ;
- **source documentée** : texte/référence, date de publication, URL officielle lorsqu'applicable ;
- **statut de vérification** (`verified`).

## Verrou de validation

La **validation définitive** d'un lot de paie est refusée (erreur métier explicite) tant que des règles
applicables à la période sont marquées non vérifiées. La **simulation**, elle, reste toujours possible —
elle produit un bulletin préfixé « SIMULATION ».

L'action *Contrôle* d'un lot liste les **anomalies bloquantes** avant validation : matricule salarié manquant,
dates de contrat incohérentes, paramètres hors fenêtre d'effet, etc.

## Jeu de référence 2025

L'action `payroll/parameter-sets/reference-2025/` charge un jeu **de référence** comprenant les cotisations
usuelles (maladie, vieillesse plafonnée/déplafonnée, chômage, retraite complémentaire AGIRC-ARRCO, CSG/CRDS,
prélèvement à la source neutre, etc.) avec pour chaque règle la source (URSSAF, BOSS, service-public.fr,
loi de financement de la sécurité sociale) et la date d'effet.

⚠️ Ce jeu est fourni à titre documenté : chaque entreprise doit le **vérifier contre les publications
officielles en vigueur** avant de le marquer « vérifié » et de valider des paies réelles. Les taux évoluent
(LFSS, arrêtés AGIRC-ARRCO…) — la responsabilité du calcul en production incombe à l'employeur.

## Cycle d'un lot de paie

1. `brouillon` → **Simuler** : calcul déterministe des bulletins (mêmes entrées ⇒ mêmes résultats).
2. `simulee` → **Valider** : refus si anomalies ou règles non vérifiées ; le lot devient immuable.
3. `validee` → *Bulletins PDF* (archivage), *DSN* (fichier préparé — voir ci-dessous), *Clôturer*.
4. `cloturee` : période fermée. Le paiement physique des salaires reste une opération bancaire **hors application**.

## DSN — statut honnête

L'action DSN produit un **fichier texte structuré et lisible** destiné à faciliter une déclaration future,
avec les événements de la période et les assiettes. Ce fichier est :

- **non transmis** (aucune connexion à net-entreprises n'est implémentée),
- **non accusé** (aucun retour d'accusé traité),
- **non certifié** (le format n'est pas garanti conforme au cahier technique DSN en vigueur).

Les DSN générées sont **archivées** avec horodatage et hash, et étiquetées explicitement dans l'interface.

## Bulletin

Le PDF du bulletin respecte la structure légale usuelle (mentions employeur, salarié, rubriques, cumuls,
net social, net à payer). Il est généré via WeasyPrint en Docker ; environnement sans Pango ⇒ repli
automatique sur un rendu ReportLab simplifié (signalé dans `docs/deploiement.md`).
