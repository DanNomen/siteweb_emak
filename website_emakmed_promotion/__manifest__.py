{
    'name': 'Website Emakmed Promotion',
    'version': '18.0.2.0.0',
    'category': 'Website',
    'summary': 'Promotions multi-types (BuyXGetY, Réduction %, Prix Spécial) sur le site Emakhealthcare',
    'author': 'HELLO DAN',
    'depends': [
        'website_emakmed',
        'sale_bxgy_promotion',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/bxgy_promotion_rule_form.xml',
        'views/website_promotions_template.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
