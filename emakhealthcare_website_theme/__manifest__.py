# -*- coding: utf-8 -*-
{
    'name': 'Emakhealthcare - Website Theme & Features',
    'version': '18.0.1.1.0',
    'category': 'Website',
    'summary': "Vues, modèles, contrôleurs et configuration du site Emakhealthcare",
    'description': """
Module de fonctionnalités du site Emakhealthcare
================================================
Ce module hérite de toutes les dépendances du site web (website, website_sale,
website_emakmed, account, stock) et contient toutes les vues, modèles
et contrôleurs du site. Il a été créé pour séparer les dépendances lourdes
du module de base emakhealthcare_website.
""",
    'author': 'Daniel Ahmed NOMEN',
    'depends': [
        'base',
        'emakhealthcare_website',
        'website',
        'website_sale',
        'website_emakmed',
        'account',
        'stock',
    ],
    'data': [
        'views/homepage_templates.xml',
        'views/marquee_banner.xml',
        'views/website_header.xml',
        'views/website_footer.xml',
        'views/products_page.xml',
        'views/categories_page.xml',
        'views/res_company_views.xml',
        'views/account_creation_templates.xml',
        'views/checkout_address_simplified.xml',
        'views/contactus_override.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
