# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.http import request


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('order_line.product_uom_qty', 'order_line.product_id')
    def _compute_cart_info(self):
        """
        Override to add session-based deferred cart quantity to the header icon.
        Real orders: super() + add session qty.
        NewId ghost orders: read directly from session.
        """
        from odoo.models import NewId  # avoid circular import at module level

        for order in self:
            if isinstance(order.id, NewId):
                # Ghost order (NewId) – read quantity straight from session
                cart_qty = 0
                if request and hasattr(request, 'session'):
                    deferred = request.session.get('deferred_cart', {})
                    cart_qty = sum(int(q) for q in deferred.values())
                order.cart_quantity = cart_qty
                order.only_services = False
            else:
                super(SaleOrder, order)._compute_cart_info()
                # Add any un-committed session qty on top of the real order qty
                if request and hasattr(request, 'session'):
                    deferred = request.session.get('deferred_cart', {})
                    order.cart_quantity += int(sum(deferred.values()))

    def _check_order_line_company_id(self):
        """
        Skip the cross-company product validation when the order was created
        for rendering purposes (ghost/temporary order flagged via context).
        """
        if self.env.context.get('skip_product_company_check'):
            return
        return super()._check_order_line_company_id()

    def _is_cart_ready(self):
        """
        Check if the cart is ready for checkout.
        For NewId (ghost orders), verify from in-memory order_line without DB queries.
        """
        from odoo.models import NewId
        self.ensure_one()
        if isinstance(self.id, NewId):
            return bool(self.order_line) and all(
                line.product_id and line.product_id.sale_ok 
                for line in self.order_line
            )
        return super()._is_cart_ready()
