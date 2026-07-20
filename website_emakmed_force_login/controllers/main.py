# -*- coding: utf-8 -*-
import logging

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


class EmakmedForceLogin(WebsiteSale):

    # ------------------------------------------------------------------
    # Intercept /shop/checkout — redirect guests to auth page
    # Only active on the Emakhealthcare website
    # ------------------------------------------------------------------
    @http.route(['/shop/checkout'], type='http', auth='public',
                website=True, sitemap=False)
    def shop_checkout(self, **post):
        if (request.website.name == 'Emakhealthcare'
                and request.env.user._is_public()):
            return request.redirect(
                '/emakmed/auth?redirect=/shop/cart'
            )
        return super().shop_checkout(**post)

    # ------------------------------------------------------------------
    # Custom auth page: login + register
    # ------------------------------------------------------------------
    @http.route(['/emakmed/auth'], type='http', auth='public',
                website=True, sitemap=False)
    def emakmed_auth(self, redirect='/shop/cart', **kwargs):
        # If already logged in, go directly to the redirect target
        if not request.env.user._is_public():
            return request.redirect(redirect)

        # Check if signup is allowed on this website
        signup_enabled = request.env['ir.config_parameter'].sudo().get_param(
            'auth_signup.invitation_scope', 'b2c'
        ) == 'b2c'

        values = {
            'redirect': redirect,
            'signup_enabled': signup_enabled,
            'error': kwargs.get('error', ''),
            'error_message': kwargs.get('error_message', ''),
        }
        return request.render(
            'website_emakmed_force_login.auth_page', values
        )


from odoo.addons.auth_signup.controllers.main import AuthSignupHome


class EmakmedForceLoginHome(AuthSignupHome):

    def _restore_deferred_cart(self, saved_cart):
        """Restore the deferred cart into the (potentially rotated) session."""
        if saved_cart:
            request.session['deferred_cart'] = saved_cart
            request.session['website_sale_cart_quantity'] = sum(saved_cart.values())
            try:
                request.session.modified = True
            except Exception:
                pass

    @http.route()
    def web_login(self, *args, **kw):
        # 1. Save cart before any session mutation
        saved_cart = dict(request.session.get('deferred_cart', {}))

        # 2. Prevent Odoo's standard cart from interfering (no real sale.order)
        request.session.pop('sale_order_id', None)

        # 3. Perform the actual login
        response = super(EmakmedForceLoginHome, self).web_login(*args, **kw)

        # 4. After login, restore the cart in the new session
        self._restore_deferred_cart(saved_cart)

        # 5. On Emakhealthcare, if login was successful (session.uid set),
        #    redirect to /shop/cart so the user sees their items
        if (request.session.uid
                and getattr(request, 'website', None)
                and request.website.name == 'Emakhealthcare'
                and request.httprequest.method == 'POST'):
            redirect = kw.get('redirect') or request.params.get('redirect') or '/shop/cart'
            if redirect not in ('/shop/cart',):
                redirect = '/shop/cart'
            return request.redirect(redirect)

        return response

    @http.route()
    def web_auth_signup(self, *args, **kw):
        # 1. Save cart before any session mutation
        saved_cart = dict(request.session.get('deferred_cart', {}))

        # 2. Prevent Odoo's standard cart from interfering
        request.session.pop('sale_order_id', None)

        # 3. Perform signup
        response = super(EmakmedForceLoginHome, self).web_auth_signup(*args, **kw)

        # 4. Restore cart
        self._restore_deferred_cart(saved_cart)

        # 5. On Emakhealthcare, redirect to cart after successful signup
        if (request.session.uid
                and getattr(request, 'website', None)
                and request.website.name == 'Emakhealthcare'
                and request.httprequest.method == 'POST'):
            return request.redirect('/shop/cart')

        return response
