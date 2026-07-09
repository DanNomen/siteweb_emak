# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import math

class PromotionsController(http.Controller):

    @http.route('/promotions', auth="public", website=True, sitemap=True)
    def promotions(self, page=1, **kw):
        """Page de liste des produits en promotion avec stock > 0."""
        ProductTemplate = request.env['product.template'].sudo()
        
        # On recherche les articles qui ont le ruban 'Promotion'
        # ou dont la date de début de promotion est définie
        # ET dont le stock disponible est > 0
        domain = [
            ('website_published', '=', True),
            '|',
            ('website_ribbon_id.name', 'ilike', 'Promotion'),
            ('promotion_start_date', '!=', False)
        ]

        PRODUCTS_PER_PAGE = 12
        
        # Récupérer tous les produits correspondant au domaine, avec le contexte de TOUTES les sociétés
        all_companies = request.env['res.company'].sudo().search([])
        all_products = ProductTemplate.with_context(allowed_company_ids=all_companies.ids).search(domain, order='name asc')
        
        # Filtrer ceux avec stock > 0 toutes sociétés confondues
        products_in_stock = all_products.filtered(
            lambda p: p.type == 'service' or p.qty_available > 0
        )
        
        product_count = len(products_in_stock)
        pager_pages = math.ceil(product_count / PRODUCTS_PER_PAGE) or 1
        current_page = max(1, min(int(page), pager_pages))
        offset = (current_page - 1) * PRODUCTS_PER_PAGE

        products = products_in_stock[offset:offset + PRODUCTS_PER_PAGE]

        values = {
            'products': products,
            'page': current_page,
            'page_count': pager_pages,
            'product_count': product_count,
        }
        return request.render("my_website_customer_portal.promotions_page", values)
