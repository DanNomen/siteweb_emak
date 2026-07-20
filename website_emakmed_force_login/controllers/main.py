# -*- coding: utf-8 -*-
import logging
import threading

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)

_thread_local = threading.local()


class EmakmedForceLogin(WebsiteSale):

    @http.route(['/shop/checkout'], type='http', auth='public',
                website=True, sitemap=False)
    def shop_checkout(self, **post):
        if (request.website.name == 'Emakhealthcare'
                and request.env.user._is_public()):
            return request.redirect(
                '/emakmed/auth?redirect=/shop/cart'
            )
        return super().shop_checkout(**post)

    @http.route(['/emakmed/auth'], type='http', auth='public',
                website=True, sitemap=False)
    def emakmed_auth(self, redirect='/shop/cart', **kwargs):
        if not request.env.user._is_public():
            return request.redirect(redirect)

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

    def _save_deferred_cart(self):
        existing = getattr(_thread_local, 'emak_saved_cart', None)
        if existing is not None:
            return existing
        return dict(request.session.get('deferred_cart', {}))

    def _restore_deferred_cart(self, saved_cart):
        if saved_cart:
            request.session['deferred_cart'] = saved_cart
            request.session['website_sale_cart_quantity'] = sum(saved_cart.values())
            try:
                request.session.modified = True
            except Exception:
                pass
            _logger.info(
                "Emakhealthcare: deferred_cart restored after auth (%d items)", 
                sum(saved_cart.values())
            )

    def _login_redirect(self, uid, redirect=None):
        """
        Intercepte la redirection standard post-login/signup.
        Si l'utilisateur a un panier (deferred_cart), on le force toujours
        vers le panier, peu importe d'autres overrides.
        """
        saved_cart = getattr(_thread_local, 'emak_saved_cart', None) or request.session.get('deferred_cart')
        if saved_cart:
            # Force redirect vers le panier si panier non vide
            return '/shop/cart'
        return super()._login_redirect(uid, redirect=redirect)

    @http.route()
    def web_login(self, *args, **kw):
        saved_cart = self._save_deferred_cart()

        # Blocage de Odoo natif (évite le crash _update_address)
        request.session.pop('sale_order_id', None)

        response = super(EmakmedForceLoginHome, self).web_login(*args, **kw)

        self._restore_deferred_cart(saved_cart)
        
        # Redirection forte post-login si on a un panier
        if request.session.uid and request.httprequest.method == 'POST' and saved_cart:
            return request.redirect('/shop/cart')

        return response

    @http.route()
    def web_auth_signup(self, *args, **kw):
        saved_cart = dict(request.session.get('deferred_cart', {}))
        _thread_local.emak_saved_cart = saved_cart

        request.session.pop('sale_order_id', None)

        try:
            response = super(EmakmedForceLoginHome, self).web_auth_signup(*args, **kw)
        finally:
            _thread_local.emak_saved_cart = None

        self._restore_deferred_cart(saved_cart)
        
        # Redirection forte post-signup si on a un panier
        if request.session.uid and request.httprequest.method == 'POST' and saved_cart:
            return request.redirect('/shop/cart')

        return response
