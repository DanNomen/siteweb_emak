# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Désactivation de la vérification inter-société sur le produit de la ligne de facture.
    # Cela permet à une société (ex: Emakhealthcare) de facturer un produit
    # qui appartient physiquement à une autre société (ex: Appromed).
    product_id = fields.Many2one(check_company=False)
