# -*- coding: utf-8 -*-
{
    'name': 'Emakhealthcare - Force Login at Checkout',
    'version': '18.0.1.0.0',
    'category': 'Website',
    'summary': 'Force les visiteurs non connectés à créer un compte ou se connecter avant de passer commande (site Emakhealthcare uniquement)',
    'description': """
        Intercepte le bouton "Passer la commande" pour les utilisateurs non authentifiés
        et les redirige vers une page de connexion/inscription dédiée.
        
        Uniquement actif sur le site Emakhealthcare — les autres sites ne sont pas affectés.
    """,
    'author': 'HELLO DAN',
    'depends': ['website_sale', 'auth_signup'],
    'data': [
        'views/auth_page_template.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
