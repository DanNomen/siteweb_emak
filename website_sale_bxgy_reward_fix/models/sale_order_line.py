# -*- coding: utf-8 -*-
from odoo import api, models

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_id', 'product_uom', 'product_uom_qty')
    def _compute_price_unit(self):
        super()._compute_price_unit()
        for line in self:
            if line.is_bxgy_reward:
                line.price_unit = 0.0
