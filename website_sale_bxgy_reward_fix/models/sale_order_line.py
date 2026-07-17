# -*- coding: utf-8 -*-
from odoo import models, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_id', 'product_uom', 'product_uom_qty')
    def _compute_price_unit(self):
        super()._compute_price_unit()
        for line in self:
            if hasattr(line, 'is_bxgy_reward') and line.is_bxgy_reward:
                line.price_unit = 0.0

    def _is_not_sellable_line(self):
        """
        Overridden to treat BXGY reward lines as not sellable.
        This automatically hides the quantity selector input (+ / - buttons)
        in the website_sale cart lines template.
        """
        res = super()._is_not_sellable_line()
        # If it's a reward line, don't allow modifying quantity manually
        if hasattr(self, 'is_bxgy_reward') and self.is_bxgy_reward:
            return True
        return res
