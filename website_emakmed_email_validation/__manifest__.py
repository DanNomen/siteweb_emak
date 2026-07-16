# -*- coding: utf-8 -*-
{
    'name': 'Website Emakmed Email Validation',
    'version': '1.0',
    'author': 'Fa iza itooh2',
    'category': 'Website',
    'summary': 'Require email validation before placing an order',
    'description': """
        This module enforces email validation before a user can check out or confirm an order.
        If a public user tries to checkout, they are forced to login/signup.
        When they signup, an email with a validation link is sent.
        Until the email is validated, they cannot proceed with checkout.
    """,
    'depends': ['website_sale', 'auth_signup', 'website_emakmed'],
    'data': [
        'data/mail_template_data.xml',
        'views/res_users_views.xml',
        'views/website_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
