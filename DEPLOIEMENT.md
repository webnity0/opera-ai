# Déploiement OPERA AI 1.0 Beta

Ne pas remplacer l'application publique 0.3 sans prévoir PostgreSQL et les variables d'environnement. Conserver une sauvegarde de la version 0.3. L'ancienne démo stockait les données fictives dans le navigateur; la bêta repart avec une base serveur séparée.

Sur Render : ajouter `DATABASE_URL` vers une base PostgreSQL persistante; ajouter `SECRET_KEY` (valeur aléatoire de 48 caractères ou plus); garder `COOKIE_SECURE=1`; déclencher Manual Deploy > Deploy latest commit.

Cette version ne doit pas être commercialisée ni recevoir des données clients avant validation de la sécurité et du RGPD.
