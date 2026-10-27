# Limites assumées — état honnête de chaque brique

Trois niveaux sont distingués dans tout le projet :

1. **Conçu et préparé** — structure, API, flux et tests en place, vérifiables dans le code.
2. **Validé par tests automatisés** — comportement couvert par la suite pytest (68 tests) / Vitest (5 tests).
3. **Certifié / prouvé par intégration réelle** — rien n'entre dans cette catégorie à ce stade par défaut.

| Brique | État | Détail |
|---|---|---|
| Moteur de paie | Conçu + testé | Calculs déterministes couverts par tests ; **paramètres à vérifier par vos soins** avant production (aucun taux n'est garanti à jour) |
| DSN | Conçu | Fichier structuré + archivage ; **non transmis, non accusé, non certifié** — aucune intégration net-entreprises |
| Export comptable | Conçu + testé | Format « préparé pour expert-comptable » (FEC-like) ; **non certifié** au sens de l'art. A47 A-1 |
| Facture électronique | Préparé | Config + flux prévus ; **aucune PDP** n'est intégrée : le PDF n'est **pas** une facture électronique au sens de la réforme 2026 |
| Signatures de contrats | Préparé | Archivage de documents + traçabilité ; **pas de signature électronique qualifiée** (prestataire eIDAS requis) |
| Trésorerie | Conçu + testé | Aucune connexion bancaire en écriture ; prévisionnels = calculs sur données saisies + hypothèses documentées |
| Assistant IA | Conçu + testé | Optionnel (désactivé par défaut) ; réponses documentaires non garanties — validation humaine obligatoire ; appels réels Ollama/CodeCraftAPI **non testés dans le sandbox** (pas de modèle ni clé disponible) |
| Conformité | Conçu | Alertes issues de **vos définitions** — pas un avis juridique, pas une couverture universelle des obligations |
| Docker | Livré, **non exécuté au moment de la rédaction** | Checklist de validation dans `docs/deploiement.md` à exécuter avant production |
| Restauration sauvegarde | Testée (mémoire) | Flux de bytes vérifié par pytest en mémoire ; restauration fichier PostgreSQL décrite dans `docs/deploiement.md` — à tester sur votre machine Docker |
| Sécurité | Appliquée | Argon2, JWT court + rotation, verrouillage login, RBAC serveur, audit immuable, clés IA chiffrées ; audit de sécurité externe **non réalisé** |

## Ce qui reste à faire avant une mise en production réelle

1. Vérifier et marquer « vérifié » le jeu de paramètres de paie contre les sources officielles du moment.
2. Exécuter la checklist Docker (`docs/deploiement.md` §7) sur une machine avec Docker Desktop.
3. Tester la sauvegarde/restauration PostgreSQL bout en bout.
4. Faire valider l'export comptable par votre expert-comptable avant usage déclaratif.
5. Intégrer une PDP si vous ciblez la facturation électronique obligatoire (2026+).
6. Réaliser un audit de sécurité indépendant avant exposition à des données réelles.
