# -*- coding: utf-8 -*-
{
    'name': "emak_purchase_ttc",
    'summary': "Gère le Prix Unitaire TTC et calcule automatiquement le Prix Unitaire HT",
    'author': "Emak",
    'category': 'Purchases',
    'version': '1.0',
    'depends': ['purchase', 'account'],
    'data': [
        'data/account_tax_data.xml',
        'views/purchase_order_views.xml',
    ],
    'license': 'LGPL-3',
}
