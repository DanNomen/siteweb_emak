# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale_deferred_cart.controllers.main import WebsiteSaleDeferred
import logging

_logger = logging.getLogger(__name__)

class WebsiteSaleStockBlock(WebsiteSaleDeferred):

    def _check_stock(self, product_id, qty):
        """ Return (success, message, limited_qty)

        Vérifie le stock disponible pour un produit en additionnant
        les quantités de TOUS les entrepôts de TOUTES les sociétés.
        Un produit n'est bloqué que si son stock total est exactement 0 (ou négatif).
        """
        product = request.env['product.product'].sudo().browse(int(product_id))
        if not product.exists():
            return False, _("Produit introuvable."), 0

        if not product.is_storable:
            # Produit consommable ou service : toujours disponible
            return True, "", qty

        # Additionner le stock de TOUS les entrepôts sans restriction
        # IMPORTANT: le contexte doit utiliser 'warehouse_id' (int), pas 'warehouse'
        try:
            all_warehouses = request.env['stock.warehouse'].sudo().search([])
            total_available = 0.0
            for wh in all_warehouses:
                wh_qty = product.with_context(warehouse_id=wh.id).free_qty
                _logger.info(
                    "Stock check: '%s' in WH '%s' (company: %s) = %s",
                    product.name, wh.name, wh.company_id.name, wh_qty
                )
                if wh_qty > 0:
                    total_available += wh_qty
        except Exception as e:
            _logger.error("Emakhealthcare: Erreur lors du calcul du stock: %s. Fallback sur stock global.", e)
            total_available = product.free_qty

        _logger.info(
            "==== STOCK CHECK TOTAL ====\nProduct: %s (ID: %s)\nRequested: %s\nTotal Available: %s\n==========================",
            product.name, product_id, qty, total_available
        )

        if total_available <= 0:
            return False, _("Désolé, %s est en rupture de stock.") % product.name, 0
        elif qty > total_available:
            return False, _("Quantité insuffisante pour %s. Maximum disponible: %g") % (product.name, total_available), total_available
        else:
            return True, "", qty


    @http.route(['/shop/cart/update'], type='http', auth="public", methods=['POST'], website=True)
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kwargs):
        """ Override with stock check """
        product_id = int(product_id)
        deferred_cart = request.session.get('deferred_cart', {})
        curr_qty = deferred_cart.get(str(product_id), 0)
        
        if set_qty:
            new_qty = int(set_qty)
        else:
            new_qty = curr_qty + int(add_qty)

        if new_qty > 0:
            success, msg, limited_qty = self._check_stock(product_id, new_qty)
            if not success:
                # We block the addition but we might allow limited qty or just block
                # For UX, we'll cap it at max available if they tried to add too much
                if limited_qty > 0:
                    set_qty = limited_qty
                    # Store message for the user
                    request.session['stock_warning'] = msg
                else:
                    # Block completely
                    # If it was already in cart, maybe keep it? Or if set_qty was 0 (add_qty), just don't add.
                    request.session['stock_warning'] = msg
                    return request.redirect("/shop/cart")

        return super(WebsiteSaleStockBlock, self).cart_update(product_id, add_qty, set_qty, **kwargs)

    @http.route(['/shop/cart/update_json'], type='json', auth="public", methods=['POST'], website=True)
    def cart_update_json(self, product_id, line_id=None, add_qty=None, set_qty=None, display=True, **kwargs):
        """ Override with stock check for AJAX """
        product_id = int(product_id)

        if request.website.name == 'Emakhealthcare':
            deferred_cart = request.session.get('deferred_cart', {})
            curr_qty = deferred_cart.get(str(product_id), 0)
        else:
            # Lire la quantité déjà dans le vrai panier (sale.order)
            order = request.website.sale_get_order()
            curr_qty = 0
            if order:
                if line_id:
                    existing_line = order.order_line.filtered(lambda l: l.id == line_id)
                else:
                    existing_line = order.order_line.filtered(lambda l: l.product_id.id == product_id and not l.display_type)
                curr_qty = sum(existing_line.mapped('product_uom_qty')) if existing_line else 0

        if set_qty is not None:
            new_qty = float(set_qty)
        elif add_qty is not None:
            new_qty = curr_qty + float(add_qty)
        else:
            new_qty = curr_qty

        if new_qty > 0:
            success, msg, limited_qty = self._check_stock(product_id, new_qty)
            if not success:
                # Return error to frontend
                res = super(WebsiteSaleStockBlock, self).cart_update_json(product_id, line_id, add_qty, set_qty, display, **kwargs)
                res['warning'] = msg
                # If we want to strictly block:
                if limited_qty < new_qty:
                    # Update to limited qty
                    res = super(WebsiteSaleStockBlock, self).cart_update_json(product_id, line_id, set_qty=limited_qty, display=display, **kwargs)
                    res['warning'] = msg
                return res

        return super(WebsiteSaleStockBlock, self).cart_update_json(product_id, line_id, add_qty, set_qty, display, **kwargs)

    @http.route(['/shop/cart'], type='http', auth="public", website=True, sitemap=False)
    def cart(self, **post):
        """ Override cart page to show session items and potential stock warnings """
        res = super(WebsiteSaleStockBlock, self).cart(**post)
        
        # Check if we have a warning in session
        warning = request.session.pop('stock_warning', None)
        if warning and hasattr(res, 'qcontext'):
            res.qcontext['stock_warning'] = warning
        
        return res

    @http.route(['/shop/checkout'], type='http', auth="public", website=True, sitemap=False)
    def shop_checkout(self, **post):
        """ Final check before creating real Order lines """
        deferred_cart = request.session.get('deferred_cart', {})
        if deferred_cart:
            for pid_str, qty in deferred_cart.items():
                success, msg, limited_qty = self._check_stock(int(pid_str), qty)
                if not success:
                    # Stock disappeared since they added to cart!
                    # Force adjustment of cart
                    if limited_qty <= 0:
                        deferred_cart.pop(pid_str, None)
                    else:
                        deferred_cart[pid_str] = limited_qty
                    request.session['deferred_cart'] = deferred_cart
                    request.session['stock_warning'] = _("Le stock a changé. Certains articles de votre panier ont été ajustés.")
                    return request.redirect("/shop/cart")
        
        return super(WebsiteSaleStockBlock, self).shop_checkout(**post)
