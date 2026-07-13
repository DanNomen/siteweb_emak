# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    # Désactivation de la vérification inter-société sur le partenaire de la facture.
    # Permet de facturer un client qui appartient formellement à une autre société
    partner_id = fields.Many2one(check_company=False)
    commercial_partner_id = fields.Many2one(check_company=False)
    partner_shipping_id = fields.Many2one(check_company=False)
