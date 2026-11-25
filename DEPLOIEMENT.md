# Déploiement OPERA AI 1.1 Pilote

1. Sauvegarder la version GitHub actuelle et la base PostgreSQL. Préférer un service Render et une base de test distincts.
2. Décompresser l'archive. Mettre les fichiers et dossiers à la racine du repository (pas dans un dossier supplémentaire). Conserver app/ et tests/ avec leur structure. Ne jamais envoyer de .env ou de secrets sur GitHub.
3. Sur Render, vérifier la branche main, Build Command `pip install -r requirements.txt`, Start Command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Variables : DATABASE_URL = Internal Database URL de PostgreSQL persistant ; SECRET_KEY = secret stable d'au moins 48 caractères ; COOKIE_SECURE = 1. Ne pas changer le secret existant sans raison. Le démarrage sur Render refuse SQLite ou une configuration de sécurité insuffisante.
5. Manual Deploy > Deploy latest commit. La nouvelle table attachments est créée au démarrage, sans modifier les colonnes existantes ; sauvegarde préalable requise.
6. Vérifier /health (version 1.1-pilot). Créer deux comptes fictifs, ajouter une entreprise, importer un petit PDF fictif, analyser, confirmer la date, télécharger, vérifier que le second compte ne voit pas le fichier, supprimer, tester export et déconnexion. Tester aussi sur mobile. Redémarrer et vérifier la persistance.
7. En cas d'échec, revenir au commit précédent ; ne pas supprimer la base ni les tables sans sauvegarde.

**Lancement autorisé uniquement en démonstration avec données fictives.** Pas d'abonnement facturé ni de données clients avant les validations décrites dans README.md.
