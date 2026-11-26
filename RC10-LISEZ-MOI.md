# RC10 — candidat de test, non commercial
Base RC9 conservée. Nouveaux chantiers, association des entreprises et pièces requises par libellé exact, alertes tableau de bord, calendrier coloré et assistant externe optionnel. Les pièces manquantes incluent les pièces expirées; aucune certification juridique.

## Déploiement
Conserver le commit RC9 et sauvegarder la base Neon avant déploiement. Charger les fichiers de cette archive à la racine du dépôt, garder Docker et les variables Render existantes. Deux nouvelles tables sont créées au démarrage. Ne pas activer Stripe live. Tester sur données fictives seulement.

## IA externe
Désactivée par défaut. Variables serveur OPENAI_API_KEY et OPERA_AI_MODEL (modèle compatible Chat Completions). Ne jamais publier la clé sur GitHub. Autorisation explicite à chaque requête; transmission de la question et des noms, types, dates, statuts des 100 premiers documents maximum. Pas de PDF brut. Limite locale 5 requêtes/10 min par IP, plafond fournisseur à configurer; ce n'est pas un plafond de facturation. Ne pas activer pour des données réelles avant revue confidentialité et contrat fournisseur. Pas d'action automatique par IA. L'API externe n'a pas été testée en direct.

## Validation
25 tests locaux réussis, 2 avertissements de dépréciation TestClient; syntaxe JavaScript vérifiée. Pas de validation navigateur, PostgreSQL réel, SMTP, Stripe live, audit indépendant ni test de charge. Portail de dépôt, import XLSX, rapports PDF et édition des chantiers restent à réaliser. Les relances automatiques existantes nécessitent SMTP et un ordonnanceur externe. Hébergement gratuit susceptible de dormir. Avant commercialisation: immatriculation, contrats, sauvegarde/restauration, sécurité, facturation et tests de bout en bout. Ne pas annoncer de fonctionnalités non disponibles.
