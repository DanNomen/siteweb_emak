# -*- coding: utf-8 -*-
{
    'name': 'Website Sale Cart Remove Button (Emakhealthcare)',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': "Renomme le bouton 'Remove' du panier et force la suppression complète de l'article au clic.",
    'description': """
        Ce module hérite du template du panier (website_sale.cart_lines) pour :
        - Renommer le lien/bouton de suppression d'une ligne en "Enlever du panier".
        - Forcer, au clic, un appel /shop/cart/update_json avec set_qty=0, afin que
          l'article soit TOUJOURS entièrement retiré du panier, quel que soit son
          comportement par défaut (décrément, etc.).
    """,
    'author': 'HELLO DAN',
    'depends': ['website_sale'],
    'data': [
        'views/website_sale_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_sale_cart_remove_button/static/src/js/force_remove.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
