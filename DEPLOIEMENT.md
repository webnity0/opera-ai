# Déploiement RC7

1. Conserver le commit 1.1 en ligne et sauvegarder les données fictives. Décompresser l'archive, importer son contenu à la racine de GitHub dans une branche de validation. Ne jamais importer de secrets. Les nouvelles tables sont créées au démarrage, aucune colonne existante supprimée ; reconnexion requise depuis 1.1.
2. Sur Render, garder le service Python existant et DATABASE_URL, SECRET_KEY (>=48), COOKIE_SECURE=1. Build : `pip install -r requirements.txt`. Start : `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Après fusion, Manual Deploy > Deploy latest commit. Vérifier les logs et `/health` (version 2.0-rc7). Tester inscription, connexion, entreprise, PDF fictif, export, relances manuelles, paramètres et isolation entre deux comptes. Redémarrer pour vérifier la persistance. Revenir au commit 1.1 si nécessaire, sans supprimer les tables.
4. OCR : le service Python peut fonctionner sans les binaires. Le Dockerfile installe Poppler et Tesseract ; tester séparément le runtime Docker sur une instance gratuite compatible, sans supprimer le service actuel ni engager de frais. Vérifier OCR dans Paramètres. Aucune obligation de changer le runtime pour le pilote.

## Intégrations facultatives — ne pas configurer pour le premier déploiement
Stripe mode test : STRIPE_SECRET_KEY (sk_test_...), STRIPE_WEBHOOK_SECRET (whsec_...), PUBLIC_URL (URL HTTPS du service). Configurer le portail de facturation test et le webhook `/webhooks/stripe` pour customer.subscription.created, updated, deleted. Tester avec les cartes de test Stripe uniquement. Aucun paiement réel n'est autorisé par ce code. Aucun abonnement client facturé.

Relances : uniquement sur adresses fictives/boîtes de test contrôlées, avec SMTP_HOST, SMTP_PORT (465 par défaut), SMTP_USER, SMTP_PASSWORD, SMTP_FROM, REMINDER_JOB_SECRET (32 caractères min.), REMINDER_ALLOWED_ACCOUNTS (e-mails des comptes pilotes autorisés séparés par virgules). Ne pas autoriser une adresse non vérifiée sur un service public. Activer les documents individuellement dans Relances. Un ordonnanceur externe doit appeler POST `/jobs/reminders` avec l'en-tête `X-Job-Secret` (secret, jamais dans le dépôt). Aucun ordonnanceur n'est installé. Tester l'envoi et les doublons avant de planifier. Le serveur gratuit peut dormir et le fournisseur peut limiter ou bloquer SMTP ; ne pas souscrire à un service payant pour contourner cela sans accord.

Ne pas utiliser de données réelles ni de paiements réels avant les validations du README.

RC4 : vérifier dans Paramètres le quota de stockage et télécharger l'export JSON. Tester un PDF fictif sur Render et surveiller mémoire/CPU. Les nouveaux modules `app/pdf_worker.py` et `app/pdf_isolation.py` doivent être présents. Aucune nouvelle variable obligatoire. Ne pas déployer en production commerciale sans les validations listées dans README.

RC5 : tester le renouvellement d’un document fictif, le remplacement de son PDF, le quota et l’export calendrier. Aucune variable supplémentaire requise. Les relances doivent être réactivées après renouvellement ou changement de contact.

RC6 : vérifier le bouton « Essayer avec des exemples fictifs » sur le tableau de bord d’un compte de test vide. Vérifier que les trois exemples n’apparaissent pas dans un autre compte. Tester la navigation et l’affichage mobile. Aucun nouvel identifiant ni changement de runtime requis pour le pilote. /health doit annoncer 2.0-rc7. Garder les paiements et envois automatiques désactivés.

## RC7 — six tarifs Stripe Sandbox
Les six Price ID test sont intégrés dans app/integrations.py. Vérifier les trois variables STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET et PUBLIC_URL=https://opera-ai-0i54.onrender.com (sans slash final). Les deux clés restent exclusivement dans Render. Le code vérifie auprès de Stripe le montant, la devise et la fréquence avant d'ouvrir Checkout. Aucun paiement live autorisé. Le webhook identifie le plan et le statut, mais le pilote reste gratuit : les droits, quotas, essais et restrictions commerciales par offre ne sont pas appliqués. Tester chaque offre avec un compte fictif distinct, vérifier le statut dans Paramètres et les livraisons du webhook Stripe. Activer le portail client dans le Sandbox si nécessaire. Tester la résiliation et les paiements échoués. Ne pas ouvrir aux clients réels.
