# -*- coding: utf-8 -*-
{
    'name': 'Relevé par Décade',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Génération automatique de relevés de factures par tranche de 10 jours (décades), groupés par client.',
    'description': """
Relevé par Décade
=================
Ce module génère automatiquement des relevés de factures tous les 10 jours.
Chaque relevé (décade) regroupe les factures (draft + posted) par client
sur une période de 10 jours.

Fonctionnalités :
- Génération automatique via cron (J10, J20, fin de mois)
- Groupement des factures par client
- Envoi email manuel par client ou en masse
- Menu dédié dans le module Facturation
    """,
    'author': 'Daniel Ahmed',
    'depends': [
        'account',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'report/report_decade_statement.xml',
        'data/ir_sequence_data.xml',
        'data/decade_statement_mail_template.xml',
        'data/decade_statement_cron.xml',
        'views/decade_statement_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
