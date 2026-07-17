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
                '/emakmed/auth?redirect=/shop/checkout'
            )
        return super().shop_checkout(**post)

    # ------------------------------------------------------------------
    # Custom auth page: login + register
    # ------------------------------------------------------------------
    @http.route(['/emakmed/auth'], type='http', auth='public',
                website=True, sitemap=False)
    def emakmed_auth(self, redirect='/shop/checkout', **kwargs):
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
