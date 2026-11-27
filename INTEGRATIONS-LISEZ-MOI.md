# Correctif Groq / Brevo — mode pilote

Remplace les fichiers du dépôt par ceux de cette archive (conserver le commit précédent et sauvegarder Neon). Aucun changement de schéma ni de prix. Ne jamais déposer les clés API dans GitHub.

## Render → Environment
- `GROQ_API_KEY` : clé Groq déjà enregistrée. Elle est prioritaire sur OpenAI ; le modèle par défaut est `openai/gpt-oss-20b` (option `GROQ_MODEL` pour le modifier). Pas de bascule silencieuse vers un service payant.
- `BREVO_API_KEY` : clé Brevo déjà enregistrée.
- `BREVO_SENDER_EMAIL` : adresse vérifiée dans Brevo (pour ce test, `webnity0@gmail.com`).
- `REMINDER_ALLOWED_ACCOUNTS` : adresse de connexion au compte pilote autorisé (dans les captures : `est-opera@example.com`).
- Garder `REMINDER_JOB_SECRET` absent pour le premier test : aucune relance automatique ne sera activée par ce correctif seul.

Enregistrer et déployer la dernière révision. Tester l'assistant avec des données fictives et vérifier le bouton **Envoyer un e-mail de test** dans Relances. Le bouton ne peut envoyer qu'un message fixe à l'expéditeur vérifié. Le succès Brevo signifie acceptation API, pas réception certaine ; vérifier la boîte de réception et les logs Brevo. Les envois Brevo de ce pilote refusent tout autre destinataire. Une tâche planifiée authentifiée et un paramétrage de production restent nécessaires pour les relances réelles. L'instance Render gratuite peut dormir.

Les API ont été simulées en tests locaux, sans clé réelle. Respecter les quotas et conditions des fournisseurs. Ne pas transmettre de données personnelles ou confidentielles. Stripe reste en Sandbox et aucun paiement réel n'est possible. Ne pas ouvrir les données clients avant validation de la sécurité et du cadre juridique.
