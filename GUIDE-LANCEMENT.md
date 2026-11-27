# OPERA AI — dossier de lancement (27 novembre 2026)

## Démonstration commerciale à 0 €
Cible : entreprises générales et contractants généraux BTP, idéalement avec 10 à 50 sous-traitants, responsable administratif ou conducteur de travaux. Vérifier ce nombre et la douleur réelle en appel. Ne pas prétendre avoir des clients ou des économies mesurées. Démonstration sur données fictives uniquement ; aucun paiement ni dépôt de document client. Proposer une liste d'attente et un rendez-vous de 10 minutes.

### Premier e-mail
Objet : Suivi des attestations de vos sous-traitants

Bonjour,
Comment suivez-vous aujourd'hui les échéances des attestations et les pièces manquantes de vos sous-traitants ? Je développe OPERA AI, un outil dédié au BTP qui centralise les documents, les échéances et les dossiers par chantier. Je cherche quelques entreprises pour recueillir leur avis sur une démonstration gratuite avec des données fictives. Seriez-vous disponible pour un échange de 10 minutes ?
Bien cordialement,
Mihai — OPERA AI
Si ce sujet ne vous concerne pas, dites-le-moi et je ne vous relancerai pas.

### Relance unique à J+5
Bonjour, je me permets de revenir vers vous au sujet du suivi documentaire des sous-traitants. Si vous êtes concerné, je peux vous montrer une démonstration courte ; sinon, aucun souci, je ne vous relancerai pas. Bien cordialement, Mihai.

### Démonstration (10 minutes)
1. Demander combien de sous-traitants et d'échéances sont suivis, avec quels outils, et combien de temps prend une relance.
2. Montrer le tableau de bord, les pièces manquantes par chantier, l'import PDF et la génération d'un rapport. Montrer l'IA et le message de relance en brouillon. Ne pas annoncer la programmation comme validée en production.
3. Demander ce qui manque, ce qu'ils paieraient, et s'ils veulent être recontactés pour un essai réel quand il sera disponible. Noter leur accord sans encaisser ni traiter leurs dossiers.

Mesures : contacts pertinents, réponses, démonstrations, intention d'essai, intention d'achat, objections, temps économisé mesuré. Commencer par 10 entreprises, puis ajuster. N'utiliser Brevo transactionnel que pour les relances de service, pas pour la prospection à froid. Vérifier les règles de prospection B2B, informer les personnes sur la source des coordonnées et leur droit d'opposition ; aucune relance après opposition.

## Documents juridiques — brouillons internes, non publiables en l'état
### Mentions légales
Éditeur : [identité et statut exacts, adresse, immatriculation, coordonnées, TVA le cas échéant]. Directeur de publication : [à compléter]. Hébergeur : [raison sociale, adresse et téléphone vérifiés]. Contact : [adresse de support]. Ne pas inventer ces éléments.
### CGV professionnelles
Objet : accès au logiciel de suivi documentaire, non certification juridique. Offre et limites : selon grille validée, prix HT, TVA selon situation. Essai : durée, accès et conditions de fin clairement annoncés avant inscription. Abonnement : période, prix total, échéance, renouvellement, modalités de changement de formule et prorata à valider. Résiliation : accessible depuis le compte, confirmation et date de fin, accès/export à préciser. Paiement : modalités, échéances, retard et indemnité applicables à valider. Support : canal, horaires et engagements réalistes. Responsabilités : validation humaine des documents et des messages ; obligations de sécurité et de service de l'éditeur ; limites proportionnées à faire valider. Disponibilité, maintenance, propriété intellectuelle, force majeure, litiges et droit applicable à compléter.
### Politique de confidentialité distincte
Identifier l'éditeur et le contact droits RGPD. Décrire comptes, facturation, logs, documents et contacts importés, finalités, bases légales, destinataires, durées et suppression, droits et réclamation CNIL. Distinguer traitements propres et traitements pour le compte des entreprises. Décrire cookies de session. L'IA externe reçoit question et certaines métadonnées (noms, types, dates, statuts), pas les PDF eux-mêmes via cette route ; vérifier contrats, régions, transferts, conservation, utilisation des données par Groq et autres prestataires. Ne pas activer sur données réelles tant que non validé.
### Accord de sous-traitance RGPD (article 28)
Annexe à compléter : objet, durée, finalités, catégories de données et personnes ; instructions documentées, confidentialité, mesures de sécurité, sous-traitants ultérieurs et autorisation, transferts, assistance droits et incidents, restitution/suppression, preuves et audits. Documenter réellement Render, Neon, Brevo, Groq et Stripe, leurs rôles et contrats. Aucun engagement fictif.
Sources : https://entreprendre.service-public.gouv.fr/vosdroits/F37351 ; https://entreprendre.service-public.gouv.fr/vosdroits/F33527 ; https://www.cnil.fr/fr/reglement-europeen-protection-donnees/chapitre4 ; https://www.cnil.fr/fr/securite-gerer-la-sous-traitance

## Revue technique limitée et conditions d'ouverture
Code inspecté : cookies sécurisés et secret minimum en mode Render, protection CSRF sur écritures, quotas et limites de requêtes, isolation organisation testée, contrôle du secret des jobs avec comparaison constante, verrou PostgreSQL anti-concurrence et déduplication par échéance/stade. Stripe refuse les clés live ; Brevo n'envoie qu'à l'expéditeur de test. L'essai de 14 jours démarre à la création du compte et n'est pas un abonnement réel. Tests SQLite et services simulés, pas un audit de production.
Risques restant à traiter : dépôt public et historique des secrets (ne jamais téléverser les clés ; passer en privé après vérification accès Render), vérification e-mail et récupération de mot de passe avant ouverture, limites anti-abus globales et multi-instance, validation des données réelles et contrats fournisseurs, restauration Neon sur une base séparée, chiffrement et rétention des documents, export complet et suppression, test mobile et accessibilité, surveillance et alertes, gestion d'erreurs et doublons en cas de panne après acceptation Brevo mais avant commit, contrôle des prix réels, événements Stripe et factures. Le service gratuit peut dormir. Le job GitHub Actions est best effort et doit être validé en conditions réelles ; aucun engagement de délai. Une entreprise déclarée et des documents juridiques complétés sont nécessaires avant la vente, sans attendre la première facturation pour vérifier les obligations applicables.

## Déclenchement des relances sans Terminal
Le workflow `.github/workflows/reminders.yml` est fourni. Vérifier qu'il est bien présent dans GitHub (les dossiers cachés peuvent être omis lors d'un upload). Il faut créer un secret GitHub Actions `REMINDER_JOB_SECRET` identique à celui de Render, jamais dans le code. Lancer manuellement Actions > Relances OPERA - pilote > Run workflow sur main. Vérifier le résultat, Gmail et Brevo. Une fois le test réussi, ajouter la variable GitHub Actions `OPERA_REMINDERS_SCHEDULE=true` pour activer le passage quotidien à 07:17 UTC. Ne pas activer avant validation ; uniquement Atlas avec adresse de test. Le job n'envoie pas de nouveau message si le même stade est déjà enregistré. Les quotas GitHub et la disponibilité des workflows planifiés restent à vérifier, et aucun service payant n'est ajouté par ce fichier.
