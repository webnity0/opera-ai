# OPERA AI 2.0 — Ultimate | Candidat de validation

OPERA AI est un outil de pilotage documentaire pour les entreprises du bâtiment et leurs sous-traitants. Cette archive reprend la RC10, ajoute des fonctionnalités métier et corrige des points de présentation. Elle reste en mode pilote : **données fictives uniquement, aucun paiement réel.** Voir `DEPLOIEMENT.md` pour le parcours de validation.

## Fonctionnalités
- Tableau de bord avec graphique circulaire et actions prioritaires ; navigation latérale, calendrier, historique, recherche, exports CSV et calendrier.
- Gestion d'entreprises et import CSV, copier-coller ou XLSX (100 lignes, 3 colonnes, aperçu à confirmer, formules refusées). Gestion de chantiers modifiables, association des entreprises et exigences documentaires. Le contrôle par chantier porte sur les types et dates renseignés, pas sur la validité juridique.
- PDF jusqu'à 10 Mio et 30 pages, analyse locale par règles et OCR français/anglais si installé, suggestions à confirmer, import groupé jusqu'à 5 fichiers. Les PDF actifs, avec formulaires ou pièces jointes restent refusés pour des raisons de sécurité ; ne pas supprimer une signature ou modifier un original officiel pour le faire accepter.
- Collecte documentaire : lien secret à usage unique valable 7 jours, associé à un document existant ; le destinataire ne voit aucune donnée du compte. Le PDF reçu ne remplace l'ancien qu'après téléchargement, vérification et validation de l'utilisateur connecté. Les liens peuvent être révoqués ; les fichiers en attente comptent dans le quota de stockage.
- Rapports PDF de suivi documentaire et des chantiers, avec avertissement de non-certification. Modèles de relance personnalisables, brouillons et historique, relances programmées sous conditions (SMTP et ordonnanceur externe).
- Assistant local déterministe, y compris suivi des chantiers ; option générative externe avec autorisation explicite, à configurer. Aucun PDF brut, coordonnées de contact, référence ni note n'est envoyé à l'IA externe par le code ; les noms d'entreprises, types, dates, états et la question sont transmis. Ne pas saisir d'information sensible. Ce n'est pas une vérification juridique.
- Six prix Stripe Sandbox (39, 69, 109 euros/mois ; 390, 690, 1090 euros/an). Essai local de 14 jours. Quotas de fiches par plan ; chantiers, collecte, IA externe et relances automatiques réservés aux essais éligibles, Professional et Business. Tous les plans ont encore une limite pilote commune de 100 PDF et 50 Mio par organisation et 400 Mio de pièces jointes globalement. Paiement réel interdit par le code.

## Démarrage local
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
COOKIE_SECURE=0 uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m pytest -q
```
Sous Render, conserver Docker et PostgreSQL ; voir le guide. `examples/OPERA-DEMO-seulement.pdf` et `examples/entreprises-demo.csv` sont des données synthétiques. Ne jamais utiliser un document réel pendant le pilote.

## Résultats vérifiés
32 tests automatisés réussis sur SQLite temporaire, dont l'OCR synthétique, les six tarifs Stripe simulés, la collecte à usage unique, l'isolation entre organisations, l'import Excel, les rapports PDF et les modèles de relance. Deux avertissements de dépréciation TestClient dans les anciens tests de cookies. Syntaxe des deux scripts JavaScript et unicité des identifiants HTML vérifiées. Le PDF d'exemple a été rendu et contrôlé. Le navigateur de test bloque les connexions locales ; aucun parcours navigateur complet ni test Render/Neon réel effectué. Stripe/SMTP et appel génératif simulés ; aucune livraison ni transaction réelle.

## Ce qui bloque la commercialisation
Revue de sécurité et traitement PDF (le processus séparé n'est pas un bac à sable système complet), migrations versionnées et sauvegarde/restauration PostgreSQL, vérification des comptes e-mail et récupération de mot de passe, tests navigateur/mobile et charge, surveillance, validation RGPD et des contrats, activation des services externes, configuration et tests Stripe live dans un environnement distinct, immatriculation, facturation et fiscalité. Les offres d'hébergement gratuites peuvent dormir. Les relances automatiques ne garantissent pas un envoi exactement une fois en cas de panne après SMTP. Aucune note de 9/10, certification, garantie de sécurité ou prévision de ventes n'est établie par ces tests.
