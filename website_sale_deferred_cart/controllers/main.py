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

        # Calculate amount using a temporary ghost order.
        #
        # IMPORTANT: previously, any exception here was silently swallowed
        # ("except Exception: pass") which left session['website_sale_cart_amount']
        # at whatever value it had from the *previous* quantity update. That is
        # why the header badge could show a stale, higher total (e.g. 40 500 CFA
        # for 3 units) while the cart page — which always recomputes the amount
        # fresh via _get_ghost_order() with no swallowed exception — correctly
        # showed the up-to-date total (e.g. 27 000 CFA for 2 units).
        #
        # We now always overwrite session['website_sale_cart_amount'] on every
        # call: on success with the freshly computed ghost order amount, and on
        # failure with a best-effort fallback computed directly from the
        # products still in the session cart, so the header is never left
        # showing a number that no longer matches the actual cart content.
        ghost_order = None
        try:
            ghost_order = self._get_ghost_order()
            request.session['website_sale_cart_amount'] = ghost_order.amount_total
        except Exception:
            _logger.exception(
                "Emakhealthcare: échec du calcul du montant via la ghost order "
                "pour deferred_cart=%s ; utilisation du montant de secours "
                "(prix catalogue x quantité) pour éviter un montant obsolète "
                "dans le badge du panier.", cart
            )
            request.session['website_sale_cart_amount'] = self._fallback_cart_amount(cart)
        finally:
            if ghost_order is not None:
                try:
                    ghost_order.unlink()
                except Exception:
                    _logger.exception(
                        "Emakhealthcare: échec du unlink() de la ghost order."
                    )

        if hasattr(request.session, 'modified'):
            request.session.modified = True

        return new_qty

    # ------------------------------------------------------------------
    # Fallback amount: used only if the ghost order computation fails, so the
    # header badge never displays a stale amount from a previous quantity.
    # This intentionally does NOT include BXGY/promotion rewards (those need
    # the ghost order to compute), it's a best-effort approximation based on
    # the pricelist unit price so the customer never sees a wildly wrong or
    # outdated total.
    # ------------------------------------------------------------------
    def _fallback_cart_amount(self, deferred_cart):
        try:
            product_ids = [int(pid) for pid in deferred_cart.keys()]
            if not product_ids:
                return 0.0
            products = request.env['product.product'].sudo().browse(product_ids).exists()
            pricelist = request.website.pricelist_id
            total = 0.0
            for product in products:
                qty = deferred_cart.get(str(product.id), 0)
                price = product.with_context(
                    pricelist=pricelist.id if pricelist else False
                )._get_contextual_price() if hasattr(product, '_get_contextual_price') else product.lst_price
                total += price * float(qty)
            return total
        except Exception:
            _logger.exception(
                "Emakhealthcare: échec du calcul du montant de secours ; "
                "retour à 0 pour éviter d'afficher un montant obsolète."
            )
            return 0.0

    # ------------------------------------------------------------------
    # BXGY reward preview: same logic as sale_bxgy_promotion._recompute_bxgy_rewards
    # but without ever writing to the database, since the ghost order is a
    # pure in-memory (.new()) record and SaleOrderLine.create() would fail
    # (or write against a fake order_id) if used here.
    # ------------------------------------------------------------------
    def _get_bxgy_preview_reward_lines(self, order, qty_by_product):
        """Compute the (0, 0, {...}) command tuples for the BXGY reward lines
        that sale_bxgy_promotion would normally create in DB, so they can be
        appended to the ghost order's in-memory order_line instead."""
        reward_line_cmds = []

        if not hasattr(order, "_get_bxgy_applicable_rules"):
            # sale_bxgy_promotion not installed
            return reward_line_cmds

        rules = order._get_bxgy_applicable_rules()
        if not rules:
            return reward_line_cmds

        grouped_rules = {}
        for rule in rules:
            key = order._same_products_key(rule)
            if not key:
                continue
            grouped_rules.setdefault(key, order.env["bxgy.promotion.rule"])
            grouped_rules[key] |= rule

        for key, sibling_rules in grouped_rules.items():
            purchased_qty = sum(qty_by_product.get(pid, 0.0) for pid in key)
            if purchased_qty <= 0:
                continue

            best_rule = order._get_best_bxgy_rule_for_qty(sibling_rules, purchased_qty)
            if not best_rule:
                continue
            best_rule = best_rule[0]

            multiplier = order._compute_reward_multiplier_for_rule(best_rule, purchased_qty)
            if multiplier <= 0:
                continue

            for reward_line in best_rule.reward_line_ids:
                if not reward_line.product_id or reward_line.quantity <= 0:
                    continue

                reward_qty = multiplier * reward_line.quantity
                if reward_qty <= 0:
                    continue

                reward_line_cmds.append((0, 0, {
                    'product_id': reward_line.product_id.id,
                    'product_uom_qty': reward_qty,
                    'price_unit': 0.0,
                    'name': "%s (Promotion)" % reward_line.product_id.display_name,
                    'is_bxgy_reward': True,
                    'bxgy_rule_id': best_rule.id,
                }))

        return reward_line_cmds

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
            qty_by_product = {}
            for pid_str, qty in deferred_cart.items():
                product = product_map.get(int(pid_str))
                if not product:
                    continue
                lines.append((0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': qty,
                    'name': product.display_name,
                }))
                qty_by_product[product.id] = qty_by_product.get(product.id, 0.0) + qty

            if lines:
                # Ajout initial pour que l'ORM puisse évaluer la règle
                order.update({'order_line': lines})
                
                reward_line_cmds = self._get_bxgy_preview_reward_lines(order, qty_by_product)
                if reward_line_cmds:
                    # Pour éviter la duplication sur un enregistrement en mémoire (NewId),
                    # on vide toutes les lignes existantes avec (5, 0, 0) et on recrée tout.
                    order.update({'order_line': [(5, 0, 0)] + lines + reward_line_cmds})

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
                    # Prendre la vraie quantité du panier (incluant les cadeaux BXGY)
                    # Explicitement calculé car order.cart_quantity échoue sur un objet NewId
                    cart_qty = int(sum(line.product_uom_qty for line in order.order_line if line.product_id.type != 'service'))
                    _logger.warning("cart_update_json (display=False): deferred_cart=%s, order_lines=%s, cart_qty=%s, amt=%s", cart, order.order_line, cart_qty, amt)
                finally:
                    try:
                        order.unlink()
                    except Exception:
                        pass
                return {'cart_quantity': cart_qty, 'quantity': new_qty, 'amount': amt, 'cart_ready': True}
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
            # Sauvegarder le montant avant la suppression (unlink) de la ghost order
            final_amount = order.amount_total
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
            'amount': final_amount,
            # cart_ready MUST be True in the JSON response so that Odoo's
            # updateCartNavBar() (website_sale_utils.js) removes the 'disabled'
            # class from the "Passer la commande" button. Without this key the
            # button stays disabled after every AJAX quantity update.
            'cart_ready': True,
        }
        
        try:
            # Payment utils might not be easily importable here, so we mimic standard behavior
            res['minor_amount'] = int(final_amount * 100) # simplified minor amount
        except Exception:
            pass

        return res

    @http.route(['/shop/cart'], type='http', auth="public",
                website=True, sitemap=False)
    def cart(self, **post):
        """Cart page – render from session."""
        if request.website.name != 'Emakhealthcare':
            return super(WebsiteSaleDeferred, self).cart(**post)
        
        deferred_cart = request.session.get('deferred_cart', {})
        _logger.warning("CART ROUTE CALLED: user=%s, deferred_cart=%s, session_keys=%s", request.env.user.login, deferred_cart, list(request.session.keys()))

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