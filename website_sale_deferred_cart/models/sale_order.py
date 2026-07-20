# -*- coding: utf-8 -*-
import logging

from odoo import models, api
from odoo.http import request

_logger = logging.getLogger(__name__)


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
        Override to support NewId "ghost" orders (created via .new() in
        WebsiteSaleDeferred._get_ghost_order()) used to render the cart/checkout
        pages before anything is committed to the database.

        The base Odoo implementation of _is_cart_ready() relies on checks that
        assume a persisted record (real DB id) — e.g. querying related stock or
        line records by id. On a NewId ghost order this either raises or falls
        through to False, which is why the "Passer la commande" button was
        turning grey/disabled as soon as the cart quantity changed, even though
        the cart was perfectly valid.

        For ghost orders we instead do a lightweight, in-memory readiness check:
        the order is "ready" as long as it has at least one order line with a
        strictly positive quantity. Real (persisted) orders keep the standard
        Odoo behaviour.
        """
        from odoo.models import NewId  # avoid circular import at module level

        for order in self:
            if isinstance(order.id, NewId):
                try:
                    ready = bool(order.order_line) and all(
                        line.product_uom_qty > 0
                        for line in order.order_line
                        if not line.display_type
                    )
                except Exception:
                    _logger.exception(
                        "Emakhealthcare: erreur lors du calcul de _is_cart_ready "
                        "sur une ghost order (NewId) ; commande considérée comme "
                        "non prête par sécurité."
                    )
                    ready = False
                if len(self) == 1:
                    return ready
                if not ready:
                    return False
            else:
                result = super(SaleOrder, order)._is_cart_ready()
                if len(self) == 1:
                    return result
                if not result:
                    return False
        return True