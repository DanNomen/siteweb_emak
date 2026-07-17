# -*- coding: utf-8 -*-
from odoo import models

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

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
