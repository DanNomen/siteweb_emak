# -*- coding: utf-8 -*-
import logging
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleDeferred(WebsiteSale):

    # ------------------------------------------------------------------
    # Helper: get all authorized company IDs for cross-company stock
    # ------------------------------------------------------------------
    def _get_authorized_company_ids(self):
        """Return IDs of all companies that authorised stock sharing with emakhealthcare."""
        companies = request.env['res.company'].sudo().search([
            ('authorize_emakhealthcare_stock', '=', True),
        ])
        ids = companies.ids
        if not ids:
            ids = [request.website.company_id.id]
        return ids

    # ------------------------------------------------------------------
    # Session cart helpers
    # ------------------------------------------------------------------
    def _deferred_cart_update(self, product_id, add_qty=1, set_qty=None):
        """Update the session cart and return new_qty."""
        product_id = int(product_id)
        if 'deferred_cart' not in request.session:
            request.session['deferred_cart'] = {}

        cart = request.session['deferred_cart']
        pid = str(product_id)
        curr_qty = cart.get(pid, 0)

        if set_qty is not None:
            new_qty = int(set_qty)
        else:
            new_qty = curr_qty + int(add_qty)

        if new_qty <= 0:
            cart.pop(pid, None)
            new_qty = 0
        else:
            cart[pid] = new_qty

        request.session['deferred_cart'] = cart
        request.session['website_sale_cart_quantity'] = sum(cart.values())
        if hasattr(request.session, 'modified'):
            request.session.modified = True

        return new_qty

    # ------------------------------------------------------------------
    # Ghost order: temporary real order created & unlinked per request
    # ------------------------------------------------------------------
    def _get_ghost_order(self):
        """
        Create a temporary in-memory Sale Order that is used ONLY for rendering.
        We use .new() instead of .create() so nothing is EVER written to the database.
        This completely bypasses the AccessError on sale.order.line for guest users
        during the final transaction flush.
        """
        deferred_cart = request.session.get('deferred_cart', {})

        # Collect all authorized company IDs so cross-company products pass validation
        allowed_company_ids = self._get_authorized_company_ids()

        new_context = dict(request.env.context,
                           allowed_company_ids=allowed_company_ids,
                           skip_product_company_check=True)
        sudo_env = request.env(su=True, context=new_context)

        # Partenaire : si l'utilisateur est connecté on prend son partenaire,
        # sinon on prend le partenaire public du site web.
        user = request.env.user
        if user and not user._is_public():
            try:
                partner_id = user.partner_id.id
            except Exception:
                partner_id = request.website.user_id.partner_id.id
        else:
            partner_id = request.website.user_id.partner_id.id

        # Use .new() to create a purely in-memory record (NewId)
        order = sudo_env['sale.order'].new({
            'website_id': request.website.id,
            'company_id': request.website.company_id.id,
            'partner_id': partner_id,
            'pricelist_id': request.website.pricelist_id.id if request.website.pricelist_id else False,
        })

        if deferred_cart:
            product_ids = [int(pid) for pid in deferred_cart.keys()]
            products = sudo_env['product.product'].browse(product_ids).exists()
            product_map = {p.id: p for p in products}

            lines = []
            for pid_str, qty in deferred_cart.items():
                product = product_map.get(int(pid_str))
                if not product:
                    continue
                lines.append((0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': qty,
                    'name': product.display_name,
                }))

            if lines:
                order.update({'order_line': lines})

        _logger.info(
            "Ghost order (NewId) created in memory for %d session products",
            len(deferred_cart)
        )
        return order

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @http.route(['/shop/cart/update'], type='http', auth="public",
                methods=['POST'], website=True)
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kwargs):
        """Store cart in session instead of database."""
        if request.website.name != 'Emakhealthcare':
            return super(WebsiteSaleDeferred, self).cart_update(
                product_id, add_qty, set_qty, **kwargs
            )
        self._deferred_cart_update(
            product_id,
            add_qty=add_qty,
            set_qty=int(set_qty) if set_qty else None,
        )
        return request.redirect("/shop/cart")

    @http.route(['/shop/cart/update_json'], type='json', auth="public",
                methods=['POST'], website=True)
    def cart_update_json(self, product_id, line_id=None, add_qty=None,
                         set_qty=None, display=True, **kwargs):
        """AJAX cart update – works from session, returns rendered snippets."""
        if request.website.name != 'Emakhealthcare':
            return super(WebsiteSaleDeferred, self).cart_update_json(
                product_id, line_id, add_qty, set_qty, display, **kwargs
            )
        new_qty = self._deferred_cart_update(
            product_id, add_qty=add_qty, set_qty=set_qty
        )
        cart = request.session.get('deferred_cart', {})

        if not display:
            order = self._get_ghost_order()
            try:
                amt = order.amount_total
            finally:
                try:
                    order.unlink()
                except Exception:
                    pass
            return {'cart_quantity': sum(cart.values()), 'quantity': new_qty, 'amount': amt}
        order = self._get_ghost_order()
        try:
            render_ctx = {
                'website_sale_order': order,
                'date': fields.Date.today(),
                'suggested_products': [],
            }
            if hasattr(self, '_get_express_shop_payment_values'):
                render_ctx.update(self._get_express_shop_payment_values(order))

            cart_lines_html = request.env['ir.ui.view']._render_template(
                "website_sale.cart_lines", render_ctx
            )
            total_html = request.env['ir.ui.view']._render_template(
                "website_sale.total", render_ctx
            )
            notification = self._get_cart_notification_information(
                order, [int(product_id)]
            )
        finally:
            # Always unlink the ghost order – we never want it to persist
            try:
                order.unlink()
            except Exception:
                pass

        res = {
            'cart_quantity': sum(cart.values()),
            'quantity': new_qty,
            'line_id': int(product_id),
            'website_sale.cart_lines': cart_lines_html,
            'website_sale.total': total_html,
            'notification_info': notification,
        }
        if 'minor_amount' in render_ctx:
            res['minor_amount'] = render_ctx['minor_amount']
        if 'amount' in render_ctx:
            res['amount'] = render_ctx['amount']

        return res

    @http.route(['/shop/cart'], type='http', auth="public",
                website=True, sitemap=False)
    def cart(self, **post):
        """Cart page – render from session."""
        if request.website.name != 'Emakhealthcare':
            return super(WebsiteSaleDeferred, self).cart(**post)
        deferred_cart = request.session.get('deferred_cart', {})
        if not deferred_cart:
            return super().cart(**post)

        order = self._get_ghost_order()
        try:
            values = {
                'website_sale_order': order,
                'date': fields.Date.today(),
                'suggested_products': [],
            }
            if hasattr(self, '_get_express_shop_payment_values'):
                values.update(self._get_express_shop_payment_values(order))
                
            html = request.env['ir.ui.view']._render_template("website_sale.cart", values)
            return request.make_response(html)
        finally:
            try:
                order.unlink()
            except Exception:
                pass

    @http.route(['/shop/checkout'], type='http', auth="public",
                website=True, sitemap=False)
    def shop_checkout(self, **post):
        """
        Transfer session cart → real DB Sale Order before checkout.
        Called when the customer clicks 'Proceed to Checkout'.
        """
        if request.website.name != 'Emakhealthcare':
            return super(WebsiteSaleDeferred, self).shop_checkout(**post)
        deferred_cart = request.session.get('deferred_cart', {})
        if deferred_cart:
            # Récupérer ou créer la commande DB pour cette session
            order = request.website.sale_get_order(force_create=True)

            # Seulement vider les lignes si la commande est encore en draft
            # et n'a pas encore de numéro confirmé (pour éviter de perdre des données)
            if order.state == 'draft':
                order.sudo().order_line.unlink()

            # Commit session items to DB
            allowed_company_ids = self._get_authorized_company_ids()
            order_sudo = order.sudo().with_context(
                allowed_company_ids=allowed_company_ids,
                skip_product_company_check=True,
            )
            for pid_str, qty in deferred_cart.items():
                order_sudo._cart_update(product_id=int(pid_str), set_qty=qty)

            # Clear session cart – it now lives in the DB order
            request.session.pop('deferred_cart', None)
            # On laisse Odoo gérer website_sale_cart_quantity normalement
            request.session.pop('website_sale_cart_quantity', None)

        return super().shop_checkout(**post)

    @http.route(['/shop/confirmation'], type='http', auth="public",
                website=True, sitemap=False)
    def shop_payment_confirmation(self, **post):
        """Clear deferred session cart on order confirmation.
        
        On laisse Odoo gérer sale_order_id lui-même — il le fait automatiquement
        après confirmation du paiement. Forcer sa suppression ici vidait le panier
        avant que l'utilisateur n'ait fini son parcours.
        """
        request.session.pop('deferred_cart', None)
        request.session.pop('website_sale_cart_quantity', None)
        return super().shop_payment_confirmation(**post)
