# -*- coding: utf-8 -*-

from odoo.http import Controller, request, route
from odoo import http
from odoo.addons.portal.controllers.web import Home
from odoo.addons.portal.controllers.portal import CustomerPortal


class Website(Home):

    # Page d'accueil
    @http.route('/', auth="public", website=True, sitemap=True)
    def index(self, **kw):
        categories = request.env['product.public.category'].sudo().search([('parent_id', '=', False)])
        best_sellers = request.env['product.template'].sudo().get_best_selling_products(limit=4).filtered(lambda p: p.company_id == request.env.company)
        currency = request.env.company.currency_id
        value = {
            "categories": categories,
            "best_sellers":best_sellers,
            "currency": currency
        }

        return request.render("website_emakmed.homepage_template", value)
    
    # Meilleurs ventes
    @http.route('/best_sellers', auth="public", website=True, sitemap=True)
    def home_page(self, **kw):
        value = {
            "page_name": "Meilleur vente"
        }

        return request.render("website_emakmed.best_sellers_template", value)
    
    
class CustomerPortalCustom(CustomerPortal):
    @route(['/my', '/my/home'], type='http', auth="user", website=True)
    def home(self, **kw):
        return request.redirect('/')

        

