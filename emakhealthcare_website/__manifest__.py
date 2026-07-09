# -*- coding: utf-8 -*-
{
    'name': 'Emakhealthcare - Site Web (Base)',
    'version': '18.0.1.0.8',
    'category': 'Website',
    'summary': "Module de base Emakhealthcare - dépendances déplacées vers emakhealthcare_website_theme",
    'description': """
Module de base Emakhealthcare - Version épurée
===============================================
Les dépendances lourdes (website, website_sale, etc.) et toutes les vues
ont été déplacées vers le module emakhealthcare_website_theme
pour isoler les dépendances correctement.
""",
    'author': 'Emak Groupe',
    'depends': [
        'base',
    ],
    'data': [],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
