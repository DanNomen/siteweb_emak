{
    "name": "FNE Connector (DGI Côte d'Ivoire)",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations/EDI",
    "summary": "Certification des factures Odoo auprès de la plateforme FNE de la DGI de Côte d'Ivoire",
    "description": """
Connecteur Facture Normalisée Électronique (FNE)
================================================

Transmet automatiquement les factures clients Odoo à la plateforme FNE de la
Direction Générale des Impôts de Côte d'Ivoire pour certification, et récupère :

* le numéro légal de la facture (``reference``) ;
* le jeton de vérification (``token``) rendu en QR code sur le PDF ;
* le solde de stickers restant.

Gère les factures de vente, les avoirs (endpoint ``refund``) et les bordereaux
d'achat de produits agricoles.
""",
    "author": "À compléter",
    "license": "LGPL-3",
    "depends": ["account", "base_setup"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/res_config_settings_views.xml",
        "views/account_tax_views.xml",
        "views/res_partner_views.xml",
        "views/account_move_views.xml",
        "views/fne_request_log_views.xml",
        "views/report_invoice.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
