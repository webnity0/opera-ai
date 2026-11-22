# OPERA AI 0.3 — Démo publique (données fictives seulement)

Interface de suivi documentaire des sous-traitants : entreprises, échéances, recherche, filtre de statut/date, modification de date, relances manuelles, export JSON/CSV et jeu de données fictives.

**Limites :** pas d’IA réelle, pas d’authentification, pas de stockage sécurisé, pas d’envoi automatique. Les données sont stockées dans le navigateur (`localStorage`), non synchronisées entre appareils. API désactivée par défaut sur la démo publique. Ne pas saisir de données personnelles ou clients.

## Render
- Build : `pip install -r requirements.txt`
- Start : `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Root directory : vide
- Branch : main
- En cas de dépôt public non connecté, redéployer manuellement la dernière version depuis Render.

## Mise à jour depuis 0.2
La clé de stockage local passe de `opera_ai_demo_02` à `opera_ai_demo_03` : les données de démonstration précédentes ne sont pas migrées.
