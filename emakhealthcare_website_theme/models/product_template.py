# -*- coding: utf-8 -*-
"""
Extension du modèle product.template pour gérer les promotions
sur le site web Emakhealthcare.

Ajoute deux champs :
- promo_type  : type de promotion (liste déroulante)
- promo_description : texte libre pour décrire la promotion
"""
from odoo import api, fields, models


class ProductTemplateEmakhPromo(models.Model):
    _inherit = 'product.template'

    promo_type = fields.Selection(
        selection=[
            ('pct',      'Remise en pourcentage (ex: -20%)'),
            ('bogo',     '1 acheté = 1 offert'),
            ('bundle',   'Pack / Bundle (achat groupé)'),
            ('qty',      'Remise sur quantité (ex: 3 pour 2)'),
            ('free_ship','Livraison gratuite'),
            ('other',    'Autre promotion'),
        ],
        string="Type de promotion",
        tracking=True,
        help="Sélectionnez le type de promotion à afficher sur le site web.",
    )

    promo_description = fields.Char(
        string="Description de la promotion",
        help="Texte court affiché sur la vignette et la page Promotions. "
             "Ex : '1 acheté = 1 offert', '-20% jusqu'au 31/07', 'Pack famille'",
    )
