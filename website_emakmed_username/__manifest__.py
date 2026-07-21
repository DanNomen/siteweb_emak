# -*- coding: utf-8 -*-
{
    'name': "Emakmed Username Login",
    'summary': "Intègre le module login_with_username à la page d'authentification personnalisée",
    'description': """
        Ce module modifie le template de connexion/inscription (website_emakmed_force_login.auth_page)
        pour supporter le nom d'utilisateur.
    """,
    'author': "Social360",
    'category': 'Website',
    'version': '1.0',
    'depends': ['website_emakmed_force_login', 'login_with_username'],
    'data': [
        'views/auth_page_template_inherit.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
