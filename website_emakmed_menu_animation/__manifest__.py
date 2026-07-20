# -*- coding: utf-8 -*-
{
    'name': 'Emakhealthcare - Menu Animation',
    'version': '18.0.1.0.0',
    'category': 'Website',
    'summary': 'Ajoute une animation sur le menu principal (barre verte coulissante)',
    'description': """
        - Onglet actif en vert.
        - Autres en noir.
        - Ligne verte coulissante en bas du menu.
    """,
    'author': 'HELLO DAN',
    'depends': ['website', 'emakhealthcare_website_theme'],
    'data': [
        'views/header_override.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_emakmed_menu_animation/static/src/css/menu.css',
            'website_emakmed_menu_animation/static/src/js/menu.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
