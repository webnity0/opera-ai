# OPERA AI 2.0 RC9 — candidat de test

## Changements
- Centre de pilotage : anneau dynamique, légende chiffrée, état vide.
- Navigation avec icônes, espace de travail élargi, cartes tarifaires retravaillées.
- Entreprises : recherche, tableau récapitulatif, accès au dossier documentaire, import CSV (trois colonnes sans en-tête, virgule ou point-virgule), import Excel par copier-coller conservé.
- Documents : sélection/dépôt de cinq PDF maximum, analyse séquentielle, confirmation individuelle des données avant stockage. Les quotas et contrôles serveur existants restent applicables.
- Calendrier mensuel interactif des échéances.
- Assistant local : historique conversationnel de la page, distinction urgent/à anticiper. Aucun modèle génératif ni transfert externe.
- Démonstration publique filtrable sur données fictives.

## Déploiement
Sauvegarder la branche main actuelle (commit/tag de référence). Décompresser l'archive et remplacer les fichiers correspondants en conservant leur arborescence. Ne pas téléverser le ZIP lui-même. Conserver le runtime Docker, les variables d'environnement, Neon et Stripe sandbox. Déployer manuellement le nouveau commit sur Render. Vérifier `/health`, puis le compte de test existant. En cas de problème, revenir au commit précédent. Ne pas envoyer de secrets dans GitHub.

## Tests à faire sur Render
1. Vérifier les trois compteurs du graphique, le calendrier et la recherche entreprise.
2. Importer un CSV fictif sans en-tête, vérifier les doublons.
3. Déposer deux PDF fictifs, vérifier les dates proposées et confirmer chacun.
4. Tester le renouvellement et le téléchargement. Les PDF avec pièces jointes intégrées ou actions actives restent refusés intentionnellement : ne pas affaiblir le filtre.
5. Vérifier la résiliation programmée et la conservation des données.
6. Vérifier la version mobile et les temps de chargement.

## Limites
Pas de modèle IA génératif, de gestion par chantier, de rapport PDF dédié, d'import XLSX direct, de portail de dépôt externe ni de nouveau moteur de relances. La planification d'envoi existante nécessite un service mail et une tâche planifiée autorisés. Le stockage et les quotas pilote restent en place. Le navigateur de test local n'a pas pu accéder au serveur local (blocage environnemental). Les tests de bout en bout sur Render restent nécessaires. Aucun paiement réel ni document réel avant validation juridique, sécurité, sauvegardes/restauration et Stripe.
