# -*- coding: utf-8 -*-
{
    'name': 'Website Sale Stock Block',
    'version': '18.0.1.1.0',
    'category': 'Website/Website',
    'summary': 'Block adding items to cart if quantity exceeds stock',
    'description': """
        This module prevents customers from adding more items to their cart than are currently in stock.
        It integrates with the session-based cart and blocks checkout if stock becomes insufficient.
    """,
    'author': 'Daniel Ahmed NOMEN',
    'depends': ['website_sale', 'sale_stock', 'website_sale_deferred_cart'],
    'data': [
        'views/templates.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
