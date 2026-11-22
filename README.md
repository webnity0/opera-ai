# OPERA AI 1.0 Beta

Bêta fonctionnelle de suivi des sous-traitants et des échéances documentaires.

## Fonctionnel
- Inscription/connexion, mots de passe Argon2, cookie signé HttpOnly et Secure
- Espaces organisationnels isolés dans chaque requête
- Gestion des entreprises et des métadonnées de documents
- Statuts d'expiration, recherche, filtres, modèles de relance à copier
- Export CSV et journal d'actions récent
- PostgreSQL via DATABASE_URL (SQLite seulement pour développement local)

## Non disponible
- Import de fichiers PDF, stockage de documents, OCR/IA, envoi automatique d'e-mails, Stripe, invitation d'utilisateurs, réinitialisation de mot de passe.
- Pas d'audit sécurité indépendant, de sauvegardes vérifiées, ni de conformité RGPD démontrée.

## Lancer en local
```bash
pip install -r requirements.txt
COOKIE_SECURE=0 uvicorn app.main:app --reload
```

## Déployer sur Render
1. Créer une base PostgreSQL persistante, relever son **Internal Database URL**.
2. Dans le service web Render, définir `DATABASE_URL` (URL PostgreSQL), `SECRET_KEY` (long secret aléatoire stable) et `COOKIE_SECURE=1`.
3. Utiliser Build `pip install -r requirements.txt` et Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Déployer et tester `/health`, inscription, déconnexion et isolation des organisations.

**Attention** : ne déployez pas cette bêta avec SQLite sur Render Free pour de vrais clients : le disque est éphémère. Ne saisissez aucune donnée réelle/confidentielle avant revue sécurité, conformité, sauvegardes, politiques de confidentialité et processus de récupération de compte.

## Architecture
`app/main.py` : API FastAPI + modèles SQLAlchemy. `app/static/index.html` : interface autonome.

## Sécurité restant à renforcer avant commercialisation
Rate limiting, vérification e-mail, reset mot de passe, MFA, protection CSRF plus complète, migration Alembic, tests d'intrusion, isolation multi-tenant en profondeur, surveillance, sauvegardes/restauration, contrats de sous-traitance, journalisation et rétention.
