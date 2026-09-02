
{
    'name': "Tableau de Bord Direction",
    'version': '18.0.1.0.0',
    'category': 'Productivity/Dashboard',
    'summary': "Dashboard KPI pour DG/PDG : CA, marge, trésorerie, stock, créances",
    'description': """
Module de tableau de bord direction (DG/PDG)
=============================================
KPI inclus :
- Chiffre d'affaires du mois + évolution %
- Marge brute + évolution %
- Créances clients + évolution %
- Trésorerie (journaux espèces + banque)
- Valeur en stock (snapshot mensuel)
- Achats du mois
- Évolution CA sur 12 mois
- Top 5 produits vendus
- Créances par ancienneté (0-30 / 31-60 / 61-90 / 90+)
- Stock & appro : ruptures, péremptions à venir
""",
    'author': "Votre Société",
    'depends': [
        'base',
        'account',
        'sale',
        'sale_margin',
        'stock',
        'product_expiry',
        'spreadsheet_dashboard',
    ],
    'data': [
        'security/dashboard_security.xml',
        'security/ir.model.access.csv',
        'views/dashboard_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dashboard_direction/static/src/js/dashboard.js',
            'dashboard_direction/static/src/xml/dashboard.xml',
            'dashboard_direction/static/src/scss/dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
