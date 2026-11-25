# OPERA AI 2.0 RC6 — candidat de validation

SaaS de suivi documentaire des sous-traitants BTP. Aucun nouveau service payant nécessaire pour le pilote. Ne pas facturer ni importer de documents réels avant validation de sécurité et de conformité.

## Inclus
- Landing page, espace client responsive, tableau de bord, entreprises, documents, recherche, export CSV, historique, paramètres, changement du mot de passe, sessions révocables.
- PDF de 10 Mio et 30 pages maximum, quotas de stockage pilote, contrôle d'accès par organisation, extraction locale par règles, suggestions de catégorie/date/référence à confirmer. OCR français/anglais facultatif, deux premières pages des scans sans texte ; Dockerfile inclus. Aucun LLM ou appel IA externe.
- Relances manuelles et relances programmées opt-in (SMTP SSL et tâche externe requis). Comptes autorisés explicitement ; aucun envoi automatique par défaut. Les répétitions sont limitées à un envoi par étape d'échéance dans le fonctionnement normal, sans garantie exactement-une-fois en cas de panne après envoi.
- Stripe Checkout et portail en mode TEST, suivi d'abonnement via webhook signé et état vérifié auprès de Stripe. Paiements réels bloqués. Le statut d'abonnement ne restreint pas encore les droits d'accès au pilote.

## Lancer localement
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
COOKIE_SECURE=0 uvicorn app.main:app --reload
python -m pytest -q
```

## Validation et limites
Les tests locaux utilisent SQLite temporaire et simulent Stripe/SMTP : aucune transaction ou livraison réelle. OCR testé sur un scan synthétique. Chromium bloque l'accès local (ERR_BLOCKED_BY_ADMINISTRATOR) ; rendu navigateur et parcours complet non validés. PostgreSQL Neon, SMTP, Stripe test et Docker n'ont pas été testés en production. Analyse PDF dans un processus séparé avec limites de ressources, mais sans bac à sable système complet, limites de débit par processus, migrations non versionnées, pas de récupération ni de vérification d'e-mail. Avant commercialisation : audit sécurité indépendant, isolation système complète du traitement PDF, sauvegardes/restauration, surveillance, RGPD, hébergement et contrats, vérification des parcours sur mobile et ordinateur, paiement réel et droits associés, politique d'abonnement. Les offres gratuites peuvent dormir, atteindre leurs quotas ou changer. Voir DEPLOIEMENT.md.

## RC4 — améliorations validées localement
- Le traitement PDF est exécuté dans un processus enfant avec environnement filtré, limite de durée, concurrence limitée à un traitement par processus web, et limites CPU/mémoire sur Linux. Ce n'est pas un bac à sable de sécurité ; le processus conserve les permissions système du serveur. Vérifier la consommation réelle sur Render Free.
- Paramètres : affichage du quota de stockage par organisation, export JSON des métadonnées (sans fichiers PDF ni secrets). Les PDF restent téléchargeables séparément ; cet export ne remplace pas une sauvegarde complète.
- Le traitement des relances vérifie à nouveau la liste des comptes autorisés à chaque exécution et ne limite plus la sélection aux 500 premières échéances.
- 15 tests locaux réussis sur SQLite. Deux avertissements de dépréciation dans les tests de cookies. Stripe et SMTP simulés. La syntaxe JavaScript a été contrôlée avec Node. Aucun nouveau service externe obligatoire.

## RC5 — parcours de renouvellement
- Remplacement explicite du PDF et de son échéance sur une fiche existante, sans doublon ni consommation supplémentaire de quota pour l’ancien fichier. Le PDF précédent est supprimé ; le télécharger avant si nécessaire.
- Export iCalendar (.ics) des échéances, avec alarme à J-7 (selon prise en charge par le calendrier). Import ponctuel, pas de synchronisation.
- Désactivation des relances automatiques au renouvellement et au changement de destinataire ou d’entreprise ; confirmation requise pour réactiver.
- Blocage renforcé des appels Stripe avec une clé réelle, validation d’inscription et amélioration du focus clavier.
- 17 tests locaux réussis, syntaxe Python et JavaScript vérifiée. Toujours en pilote : aucune validation de production, aucun paiement réel ni audit indépendant.

## RC6 — validation avant mise en ligne
- Démonstration sur demande dans un espace vide : trois entreprises et trois échéances fictives, sans adresse de destinataire. Aucun document réel ni envoi automatique.
- Limitation de débit ajoutée à l'import PDF et contrôles de concurrence supplémentaires ; désactivation des relances si catégorie, entreprise ou échéance changent ; en-têtes navigateur renforcés.
- 19 tests locaux réussis sur SQLite, vérifications syntaxiques Python et JavaScript. Deux avertissements de dépréciation des tests de cookies. Pas de validation nouvelle en navigateur ni sur PostgreSQL/Render.
- Version destinée à un pilote public de démonstration, pas à la facturation ou au traitement de données clients réelles.
