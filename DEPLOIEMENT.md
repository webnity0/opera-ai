# OPERA AI Ultimate — déploiement de validation

## Mise à jour de ton service actuel
1. Conserve le commit en ligne (tag ou branche de sauvegarde) et réalise une sauvegarde vérifiée de la base Neon, y compris des PDF. Vérifie qu'une restauration dans une base de test fonctionne. L'export JSON ne remplace pas une sauvegarde PostgreSQL.
2. Décompresse l'archive et importe son contenu à la racine du dépôt GitHub, de préférence sur une branche de validation. Ne publie aucune clé, fichier .env ou base de données. Les tables nouvelles sont ajoutées automatiquement au démarrage ; il n'y a pas de migration destructive prévue. Ne synchronise pas le Blueprint `render.yaml` sur le service actuel ; il est fourni seulement comme référence pour un nouveau pilote.
3. Conserve le service Render existant, son runtime Docker, son URL et toutes ses variables. Le Dockerfile installera les nouvelles dépendances lors du build. Pour un déploiement isolé, utilise une base de test distincte ; ne réutilise pas la base réelle pour tester.
4. Déploie puis vérifie que `/health` annonce `2.0-ultimate`. En cas d'erreur, consulte les logs, reviens au commit précédent et conserve les tables nouvelles jusqu'à analyse. Ne supprime pas le service ni la base.

## Parcours rapide de validation dans le navigateur
- Créer un compte fictif, vérifier tableau de bord et import des exemples fictifs. Tester la navigation et la version mobile.
- Documents : choisir `examples/OPERA-DEMO-seulement.pdf` depuis le ZIP extrait. L'analyse doit proposer Assurance décennale, 31/12/2027, DEMO-2027. Confirmer la fiche. Tester téléchargement, renouvellement, suppression, stockage et analyse d'un scan synthétique. Tester également le refus d'un PDF invalide.
- Entreprises : importer le CSV inclus ou un XLSX à 3 colonnes (nom, contact, e-mail), contrôler l'aperçu avant validation. Créer et modifier un chantier, associer des sous-traitants, vérifier les pièces manquantes. Télécharger le rapport PDF depuis la vue globale.
- Collecte : avec un compte en essai ou Professional, créer un « Lien de dépôt » sur une fiche. Ouvrir le lien dans une fenêtre privée, déposer le PDF fictif. Actualiser les dépôts dans l'espace connecté ; télécharger, vérifier, valider avec la nouvelle échéance. Vérifier que le lien ne fonctionne plus et que le fichier est inaccessible depuis un autre compte. Tester la révocation.
- Relances : personnaliser les deux modèles, copier le brouillon, contrôler les substitutions et les dates. Consigner une relance uniquement si elle a effectivement été envoyée. N'utiliser que des boîtes de test contrôlées pour les envois.
- Assistant : tester les questions sur les documents expirés, les échéances et les chantiers. L'IA externe est désactivée si non configurée ou non incluse. Tester les six offres Stripe en mode Sandbox, les résiliations, paiements refusés et changements de plan. L'abonnement existant de test ne doit pas être facturé à nouveau.
- Vérifier les données après redémarrage, l'isolation de deux organisations, les exports et la restauration. Mesurer le délai d'ouverture du site après inactivité ; le plan gratuit peut dormir. Le nouvel appel Stripe réutilise des connexions HTTP, sans garantie de réduction mesurée de latence.

## Intégrations facultatives (pilote)
**Stripe :** conserver `STRIPE_SECRET_KEY` (sk_test_), `STRIPE_WEBHOOK_SECRET`, `PUBLIC_URL` HTTPS, les trois événements customer.subscription.created/updated/deleted et le portail Sandbox. Le code bloque le mode live.

**IA :** `OPENAI_API_KEY`, `OPERA_AI_MODEL` (modèle compatible Chat Completions) exclusivement dans Render. Le mode est optionnel, limité en requêtes par processus et IP ; ce n'est pas un plafond de facturation. Configurer un budget et un contrôle d'usage chez le fournisseur, vérifier le contrat et la confidentialité avant tout traitement réel. Consentement explicite requis ; aucun document brut transmis.

**Relances :** SMTP_HOST, SMTP_PORT (465 par défaut), SMTP_USER, SMTP_PASSWORD, SMTP_FROM, REMINDER_JOB_SECRET (32 caractères minimum), REMINDER_ALLOWED_ACCOUNTS (comptes pilotes explicitement autorisés). Configurer un ordonnanceur externe pour appeler POST `/jobs/reminders` avec l'en-tête secret `X-Job-Secret`. Le code ne crée pas cet ordonnanceur ; ne pas mettre les secrets dans GitHub. Tester sur des boîtes contrôlées, vérifier la disponibilité SMTP sur l'hébergement, les doublons et les échecs. Les règles par document sont à activer dans l'espace client.

## Conditions impératives pour ouvrir aux paiements réels
Immatriculation et vérification Stripe, revue juridique et confidentialité, audit technique, isolation renforcée du traitement des PDF, restauration testée, récupération et vérification des comptes, surveillance et alertes, infrastructure durable, contrôle des droits, tests navigateur et charge, environnement et clés Stripe live séparés, TVA et factures, tarifs cohérents avec les capacités réellement configurées. Retirer les avertissements pilote seulement lorsque ces critères sont satisfaits. Aucun paiement réel ni donnée client réelle avant cela.
