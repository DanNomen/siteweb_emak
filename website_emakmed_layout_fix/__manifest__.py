# -*- coding: utf-8 -*-
{
    'name': "Emakmed Layout Fix",
    'summary': "Supprime les grands espaces et shapes entre le contenu et le footer sur toutes les pages",
    'description': """
        Ce module applique un CSS global pour :
        - Supprimer les shape dividers / vagues colorées entre les sections et le footer
        - Supprimer les grands espaces (padding/margin) en bas de la zone de contenu principal
        - Aligner proprement le contenu avec le footer sur toutes les pages du site
    """,
    'author': "Social360",
    'category': 'Website',
    'version': '1.0',
    'depends': ['website'],
    'data': [],
    'assets': {
        'web.assets_frontend': [
            'website_emakmed_layout_fix/static/src/css/layout_fix.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
