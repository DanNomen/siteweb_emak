# -*- coding: utf-8 -*-
{
    'name': 'Website Sale Deferred Cart',
    'version': '1.0',
    'category': 'Website/Website',
    'summary': 'Defer sale order line creation until checkout button is clicked',
    'description': """
        This module changes the behavior of the e-commerce cart.
        Instead of creating sale order lines in the database immediately when a product is added to the cart,
        it stores them in the user session. 
        The lines are only created in the database when the user clicks on the "Checkout" button.
    """,
    'author': 'Antigravity',
    'depends': ['website_sale'],
    'data': [
        'views/templates.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
