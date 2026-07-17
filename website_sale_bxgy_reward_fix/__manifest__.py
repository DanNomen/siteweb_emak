# -*- coding: utf-8 -*-
{
    'name': 'Website Sale BXGY Reward Fix',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Fix BXGY reward price on website sale checkout',
    'description': """
        Forces the price_unit of BXGY reward lines to 0.0 when 
        ordering from the website (which otherwise recalculates the price).
    """,
    'author': 'HELLO DAN',
    'depends': ['sale_bxgy_promotion', 'website_sale'],
    'data': [],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
