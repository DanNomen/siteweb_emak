{
    'name': 'Emakhealthcare Customer Portal',
    'version': '18.0.1.1.0',
    'summary': 'Tableau de bord et menus portail client pour Emakhealthcare',
    'description': """
        - Ajoute un tableau de bord des achats mensuels pour le client connecté (/my/dashboard).
        - Gère les menus dynamiques de l'espace client.
    """,
    'category': 'Website',
    'author': 'Daniel Ahmed NOMEN',
    'depends': ['website', 'portal', 'sale', 'account', 'project'],
    'data': [
        'views/portal_dashboard_templates.xml',
        'views/hide_project_portal.xml',
        'views/checkout_address_simplified.xml',
        'views/claim_reclamation_views.xml',
        'views/claim_reclamation_template.xml',
        'views/my_officine_template.xml',
        'views/client_portal_template.xml',
        'views/promotions_page.xml',
        'data/website_menus.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
