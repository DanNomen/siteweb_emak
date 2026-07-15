# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _cart_update(self, product_id=None, line_id=None, add_qty=0, set_qty=0, **kwargs):
        """ Blocking standard Odoo cart update if stock is insufficient """
        if self.website_id.name == 'Emakhealthcare':
            # Sur Emakhealthcare, le contrôleur frontend autorise la vente si le stock 
            # est dispo dans n'importe quel entrepôt. On ne bloque pas ici.
            return super(SaleOrder, self)._cart_update(product_id, line_id, add_qty, set_qty, **kwargs)

        if product_id:
            product = self.env['product.product'].sudo().browse(int(product_id))
            if product.exists() and product.is_storable:
                # Use website warehouse context if available
                warehouse = self.website_id.warehouse_id or self.warehouse_id
                product_with_ctx = product.with_context(warehouse=warehouse.id)
                
                # Compute new quantity
                if line_id:
                    line = self.env['sale.order.line'].browse(line_id)
                    current_qty = line.product_uom_qty
                else:
                    line = self.order_line.filtered(lambda l: l.product_id.id == product.id)
                    current_qty = line.product_uom_qty if line else 0
                
                if set_qty is not None and str(set_qty).strip() != '':
                    new_qty = float(set_qty)
                elif add_qty is not None:
                    new_qty = current_qty + float(add_qty)
                else:
                    new_qty = current_qty
                
                if new_qty > product_with_ctx.virtual_available:
                   # Limit to available
                   # In a backend context, we might throw an error. In Website, it's usually handled by return.
                   # But if we are in _cart_update, we can adjust it here.
                   if product_with_ctx.virtual_available < 0:
                       requested_qty = 0
                   else:
                       requested_qty = product_with_ctx.virtual_available
                   
                   # Proceed with adjusted quantity
                   return super(SaleOrder, self)._cart_update(product_id, line_id, set_qty=requested_qty, **kwargs)

        return super(SaleOrder, self)._cart_update(product_id, line_id, add_qty, set_qty, **kwargs)
