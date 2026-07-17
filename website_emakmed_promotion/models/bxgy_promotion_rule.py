# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.exceptions import ValidationError


class BxgyPromotionRuleWebsite(models.Model):
    """Extension du modèle bxgy.promotion.rule pour le site web Emakhealthcare.
    On ajoute un champ pour la description sur la page web.
    """
    _inherit = 'bxgy.promotion.rule'

    website_description = fields.Text(
        string="Description (site web)",
        help="Courte description de l'offre affichée sur la page /promotions."
    )
