# -*- coding: utf-8 -*-
import logging
import threading

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)

# Thread-local storage to pass the saved cart between web_auth_signup and web_login
# (web_auth_signup internally calls self.web_login, so we need to bridge the saved cart)
_thread_local = threading.local()


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

    def _save_deferred_cart(self):
        """
        Save the current deferred_cart from the session.
        If web_auth_signup already saved a cart via thread-local, use that
        (to avoid overwriting with an empty cart after session rotation).
        """
        existing = getattr(_thread_local, 'emak_saved_cart', None)
        if existing is not None:
            return existing
        return dict(request.session.get('deferred_cart', {}))

    def _restore_deferred_cart(self, saved_cart):
        """Restore the deferred cart into the (potentially rotated) session."""
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

    @http.route()
    def web_login(self, *args, **kw):
        # 1. Save cart — prefer cart from web_auth_signup's thread-local if available
        saved_cart = self._save_deferred_cart()

        # 2. Prevent Odoo's standard cart from interfering (blocks _update_address crash)
        request.session.pop('sale_order_id', None)

        # 3. Determine redirect target before super() clears request.params
        redirect_target = kw.get('redirect') or request.params.get('redirect') or '/shop/cart'

        # 4. Perform the actual authentication
        response = super(EmakmedForceLoginHome, self).web_login(*args, **kw)

        # 5. Restore deferred cart into the new (rotated) session
        self._restore_deferred_cart(saved_cart)

        # 6. On successful POST login, force redirect to /shop/cart
        #    (avoids portal login_successful → homepage redirect)
        if request.session.uid and request.httprequest.method == 'POST':
            if redirect_target in ('/shop/cart', '/shop/checkout'):
                return request.redirect('/shop/cart')

        return response

    @http.route()
    def web_auth_signup(self, *args, **kw):
        # 1. Save cart NOW, before do_signup rotates the session
        saved_cart = dict(request.session.get('deferred_cart', {}))

        # 2. Store in thread-local so our web_login override uses it
        _thread_local.emak_saved_cart = saved_cart

        # 3. Prevent standard cart interference
        request.session.pop('sale_order_id', None)

        try:
            # 4. Perform signup (internally calls self.web_login → our override)
            response = super(EmakmedForceLoginHome, self).web_auth_signup(*args, **kw)
        finally:
            # 5. Always clean up thread-local
            _thread_local.emak_saved_cart = None

        # 6. Restore cart after full signup flow
        self._restore_deferred_cart(saved_cart)

        # 7. After successful signup, redirect to /shop/cart
        if request.session.uid and request.httprequest.method == 'POST':
            return request.redirect('/shop/cart')

        return response
