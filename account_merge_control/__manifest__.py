# -*- coding: utf-8 -*-
{
    'name': "Account Merge Control - Contrôle Total Fusion Comptes",
    'version': '18.0.1.0.0',
    'author': 'Dan Ahemed',
    'summary': "Surcouche de sécurité, dry-run et audit sur le wizard interne account.merge.wizard",
    'description': """
Module d'hérédité sur account.merge.wizard (module custom interne)
====================================================================
Ajoute :
- Mode simulation (dry-run) avec aperçu chiffré avant exécution réelle
- Vérification automatique des périodes comptables verrouillées
- Vérification que les comptes source/cible sont du même type et de la même société
- Exécution sécurisée dans un savepoint (rollback automatique en cas d'erreur)
- Journal d'audit complet (qui, quand, quoi, combien de lignes, soldes avant/après)
- Cas pré-configurés : APPROMED (41100000 -> 41110000, 411100 -> 41110000)
                        EMAK MED  (411100 -> 41110000)

IMPORTANT : ce module suppose que le module custom interne définit un modèle
nommé 'account.merge.wizard'. Les noms de champs ci-dessous (source_account_ids,
destination_account_id, company_id) et le nom de la méthode de confirmation
(action_merge) sont des HYPOTHÈSES à ADAPTER selon le code réel de votre wizard.
Cherchez les commentaires "# ADAPTEZ" dans le code.
    """,
    'category': 'Accounting',
    'depends': [
        'account',
        # 'votre_module_merge_custom',  # ADAPTEZ : nom technique de votre module qui définit account.merge.wizard
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_merge_wizard_views.xml',
        'views/account_merge_log_views.xml',
        'data/preconfigured_merges.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
