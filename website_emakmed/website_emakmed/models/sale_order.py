# -*- coding: utf-8 -*-
from odoo import api, fields, models, api


class SaleOrder(models.Model):
    _inherit = "sale.order"

    command_type = fields.Selection(
        selection=[('normal', "Normale"), ('extranet', "Extranet")],
        default='normal',
        string="Type de vente"
    )

    @api.model
    def create(self, vals):
        if self._context.get('from_website') or vals.get('website_id'):
            vals['command_type'] = 'extranet'
        else:
            vals['command_type'] = vals.get('command_type', 'normal')

        return super(SaleOrder, self).create(vals)