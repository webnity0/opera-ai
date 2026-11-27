# OPERA AI 2.0 Final — candidat pilote

Correctif ciblé sur Ultimate. Toujours Sandbox, données fictives uniquement.

1. Sauvegarder Neon et conserver le commit actuel. Déployer l'archive sans modifier les variables.
2. Paramètres : Actualiser le statut, puis Réactiver si résiliation programmée, choisir Professional et Changer de formule test. Le changement de formule Sandbox est sans prorata. Tester la résiliation et réactivation. Le portail Stripe reste disponible pour factures et carte.
3. Vérifier chantiers, OCR, collecte, PDF, imports, calendrier. Les fonctionnalités externes IA et relances nécessitent toujours configuration et tests réels.
4. Ne pas ouvrir les paiements réels ou les données clients : le code refuse les clés live et le pilote conserve ses avertissements. Vérifier sécurité, restauration, configuration Stripe réelle, hébergement sans mise en veille, conformité et disponibilité des fonctions promises avant commercialisation.

33 tests locaux réussis (Stripe simulé, SQLite isolé). Syntaxe JS vérifiée. Le temps de réveil Render gratuit n'est pas corrigé par ce patch. Aucun test navigateur ou service réel effectué dans cette livraison. Pas de confirmation par email de résiliation intégrée.
