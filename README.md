# OPERA AI — 1.1 Pilote

Suivi administratif des sous-traitants du bâtiment. Version pilote, destinée exclusivement aux données fictives jusqu'à validation de production.

## Fonctionnalités
- Comptes et espaces organisationnels, suivi des entreprises et échéances, tableau de bord, recherche, export CSV, historique et modèles de relance manuels.
- Import PDF (10 Mio, 30 pages, 100 fichiers par organisation en usage séquentiel), stockage binaire en base, téléchargement authentifié et suppression avec la fiche.
- Extraction locale de texte des dix premières pages : suggestions de catégorie et d'échéance explicite. Validation humaine obligatoire ; PDF scannés, dates ambiguës et documents non reconnus à renseigner manuellement. Ce moteur utilise des règles, pas un LLM ni de l'OCR.
- Protection de base : Argon2, cookies signés HttpOnly/SameSite/Secure en production, contrôle d'origine, limites de requête et de tentatives par processus, vérifications organisationnelles, export CSV protégé.

## Démarrer en local
```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
COOKIE_SECURE=0 uvicorn app.main:app --reload
```
Ouvrir http://127.0.0.1:8000. Tests : `python -m pytest -q` (base SQLite temporaire isolée). Voir DEPLOIEMENT.md pour Render.

## Limites / avant commercialisation
Stripe, abonnements, OCR, LLM, envoi automatique des relances, récupération de compte et vérification e-mail ne sont pas implémentés. Aucune promesse de conformité réglementaire ni de validation d'authenticité des attestations. La limitation de débit est locale au processus ; les sessions signées ne sont pas révoquées côté serveur au logout. Les contrôles PDF ne constituent pas un antivirus ni un bac à sable. Prévoir analyse de fichiers isolée, quotas transactionnels, protection contre les PDF malveillants, contrôle d'accès et tests indépendants, sauvegardes/restauration, migrations versionnées, surveillance, politique de confidentialité, RGPD et conditions contractuelles avant données réelles. PostgreSQL et navigateur de production non testés dans cette livraison.
