# OPERA AI — MVP indépendant v0.1

Application locale indépendante, développée avec FastAPI + SQLite + HTML/CSS/JavaScript. **Démo technique uniquement**.

## Démarrage

Installer Python 3.11+ puis, dans ce dossier :

```bash
python -m venv .venv
source .venv/bin/activate  # Windows : .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Ouvrir http://127.0.0.1:8000 dans un navigateur. La base SQLite est créée localement sous `opera.db`.

## Fonctions disponibles
- Ajouter et supprimer des entreprises sous-traitantes
- Enregistrer des types de documents, références et dates d'expiration (métadonnées uniquement)
- Voir les statuts expiré / échéance à 30 jours / valide
- Générer des modèles de relance à copier (sans envoi automatique)
- API JSON documentée à http://127.0.0.1:8000/docs

## Non inclus et limites critiques
- Pas d'authentification, de rôles ou d'isolation multi-tenant
- Pas de stockage ni de téléversement de fichiers, pas d'analyse IA
- Pas de vérification de conformité juridique ou d'authenticité des pièces
- Pas de paiements, de sauvegardes automatiques, de journal d'audit, de RGPD opérationnalisé
- **Ne pas publier sur Internet, ne pas charger de données réelles de clients.**

## Prochaines étapes
1. Entretiens avec 10 PME et validation du problème / prix
2. Authentification sécurisée, multi-tenant et contrôles d'accès
3. Stockage sécurisé et politique de conservation des fichiers
4. Analyse IA avec validation humaine et tests qualité
5. Hébergement, domaine, conformité et pilotes payants
