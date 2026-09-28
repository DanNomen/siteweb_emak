# -*- coding: utf-8 -*-
{
    'name': 'Website Emakmed - Masquer le Stock',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Masque la quantité en stock sur website_emakmed et affiche une alerte si la quantité dépasse le stock disponible',
    'description': """Website sale emakmed hide stock""",
    'author': 'Daniel Ahmed NOMENJANAHARY',
    'depends': ['website_emakmed', 'website_sale', 'sale_stock'],
    'data': [
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_emakmed_hide_stock/static/src/js/stock_alert.js',
            'website_emakmed_hide_stock/static/src/css/hide_stock.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
