# -*- coding: utf-8 -*-
{
    "name": "website_emakmed",
    "summary": "Website sale emak med",
    "description": """
        Website sale emak med
    """,
    "author": "Daniel Ahmed NOMEN",
    "website": "",
    "category": "Website/Website",
    "version": "18.0.1.1.0",
    # any module necessary for this one to work correctly
    "depends": ["base", "sale", "website_sale", "stock", "website", "portal", "account"],
    # always loaded
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Record data
        "data/categories.xml",
        "data/ribbon.xml",
        "data/ir_sequence.xml",
        # Views.
        "views/templates/homepage_template.xml",
        "views/templates/templates.xml",
        "views/product_template_views.xml",
        "views/sale_order.xml",
        "views/templates/orders_template.xml",
        "views/claim_reclamation_views.xml",
        "views/snippets/website_footer_template.xml",
        "views/snippets/website_header_template.xml",
        "views/templates/client_portal_template.xml",
        "views/templates/claim_reclamation_template.xml",
        "views/templates/my_officine_template.xml",
        # wizard
        "wizard/recap_promos_wizard_views.xml",
        # Reports
        "report/mansual_report.xml",
        "report/recap_promos_report.xml",
    ],
    "installable": True,
    "application": True,
    "assets": {
        "web.assets_frontend": [
            "website_emakmed/static/src/css/index.css",
            "website_emakmed/static/src/css/products.css",
            'website_emakmed/static/src/js/claim.js',
        ],    },
    "license": "LGPL-3",
}
