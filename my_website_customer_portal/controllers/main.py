# -*- coding: utf-8 -*-
"""
Module: my_website_customer_portal
Override du contrôleur de login pour:
1. Désactive la vérification CSRF redondante (gérée autrement en multi-site)
2. Redirige vers /my après connexion sur le site Emakhealthcare
"""
from odoo import http
from odoo.addons.web.controllers.home import Home
from odoo.http import request


class EmakhealthcareLogin(Home):

    @http.route('/web/login', type='http', auth='none', readonly=False, csrf=False)
    def web_login(self, redirect=None, **kw):
        """Override: désactive CSRF (problème multi-site) + redirect vers /my."""
        # Si l'utilisateur est déjà connecté en GET, aller directement à /my
        if request.httprequest.method == 'GET' and request.session.uid:
            return request.redirect(redirect or '/my')

        # Après login réussi (POST), on veut aller sur /my
        if not redirect:
            redirect = '/my'

        return super().web_login(redirect=redirect, **kw)


from odoo.addons.website_sale.controllers.main import WebsiteSale

class EmakhealthcareWebsiteSale(WebsiteSale):

    def _get_mandatory_address_fields(self, country_sudo):
        fields = super()._get_mandatory_address_fields(country_sudo)
        if request and hasattr(request, 'website') and request.website.name == 'Emakhealthcare':
            return {'name', 'street', 'phone'}
        return fields

    def _get_mandatory_billing_address_fields(self, country_sudo):
        fields = super()._get_mandatory_billing_address_fields(country_sudo)
        if request and hasattr(request, 'website') and request.website.name == 'Emakhealthcare':
            fields = self._get_mandatory_address_fields(country_sudo)
            fields |= set(self._get_mandatory_fields())
        return fields

    def _get_mandatory_delivery_address_fields(self, country_sudo):
        fields = super()._get_mandatory_delivery_address_fields(country_sudo)
        if request and hasattr(request, 'website') and request.website.name == 'Emakhealthcare':
            return self._get_mandatory_address_fields(country_sudo)
        return fields
