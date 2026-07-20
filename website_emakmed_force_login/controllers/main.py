# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


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

    @http.route()
    def web_login(self, *args, **kw):
        # Save the deferred cart before authentication (which might rotate or clear session state)
        deferred_cart = request.session.get('deferred_cart', {})
        
        response = super(EmakmedForceLoginHome, self).web_login(*args, **kw)
        
        # Restore the deferred cart if it was present
        if deferred_cart:
            request.session['deferred_cart'] = deferred_cart
            request.session['website_sale_cart_quantity'] = sum(deferred_cart.values())
            if hasattr(request.session, 'modified'):
                request.session.modified = True
                
        return response

    @http.route()
    def web_auth_signup(self, *args, **kw):
        deferred_cart = request.session.get('deferred_cart', {})
        response = super(EmakmedForceLoginHome, self).web_auth_signup(*args, **kw)
        if deferred_cart:
            request.session['deferred_cart'] = deferred_cart
            request.session['website_sale_cart_quantity'] = sum(deferred_cart.values())
            if hasattr(request.session, 'modified'):
                request.session.modified = True
        return response
