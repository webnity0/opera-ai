# OPERA AI RC8 — candidat de test uniquement

- Archive issue de la RC7 locale, pas du dépôt GitHub en direct.
- Garder le runtime Docker déjà configuré, les variables Render/Neon/Stripe existantes et le mode Sandbox. Ne pas remplacer le service ni la base.
- Sauvegarder le dépôt et les données avant déploiement. Examiner les différences et mettre à jour les fichiers du dépôt dans une branche de test avant fusion. Le fichier render.yaml historique décrit Python : ne pas appliquer ce blueprint au service Docker existant.
- Vérifier /health (2.0-rc8), inscription, connexion, navigation, assistant, import entreprises et quotas, OCR sur un PDF fictif, renouvellement, Stripe Sandbox et isolation. Les tests locaux utilisent SQLite, pas Neon.
- Ne pas importer de données clients réelles ni activer les paiements réels avant validation sécurité, sauvegardes, conformité et fonctionnement complet.
