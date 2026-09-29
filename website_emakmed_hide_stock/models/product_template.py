# -*- coding: utf-8 -*-
from odoo import models, api, fields, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _is_emakmed_out_of_stock(self):
        self.ensure_one()
        website = self.env['website'].get_current_website()
        if website and website.name == 'Emakhealthcare':
            return False
        product = self.product_variant_id or (self.sudo().product_variant_ids[:1] if self.product_variant_ids else False)
        if not product:
            return True
        warehouse = website.warehouse_id if website else False
        product_ctx = product.with_context(warehouse=warehouse.id) if warehouse else product
        is_storable = getattr(product_ctx, 'is_storable', False) or product_ctx.type in ('product',)
        if not is_storable:
            return False
        return product_ctx.virtual_available <= 0


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _is_emakmed_out_of_stock(self):
        self.ensure_one()
        website = self.env['website'].get_current_website()
        if website and website.name == 'Emakhealthcare':
            return False
        warehouse = website.warehouse_id if website else False
        product_ctx = self.with_context(warehouse=warehouse.id) if warehouse else self
        is_storable = getattr(product_ctx, 'is_storable', False) or product_ctx.type in ('product',)
        if not is_storable:
            return False
        return product_ctx.virtual_available <= 0
