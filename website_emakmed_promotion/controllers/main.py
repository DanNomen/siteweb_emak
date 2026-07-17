# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request


class PromotionController(http.Controller):

    @http.route('/promotions', type='http', auth="public", website=True, sitemap=True)
    def promotions(self, **kw):
        """Page publique listant toutes les promotions actives du site Emakhealthcare,
        regroupées par type : BuyXGetY.
        """
        today = fields.Date.today()

        # Filtre de base : actives + publiées sur le web + dates valides
        domain = [
            ('website_published', '=', True),
            ('active', '=', True),
            '|', ('start_date', '=', False), ('start_date', '<=', today),
            '|', ('end_date', '=', False), ('end_date', '>=', today),
        ]

        all_rules = request.env['bxgy.promotion.rule'].sudo().search(
            domain, order='sequence asc, id desc'
        )

        # --- Règles Buy X Get Y ---
        bxgy_rules = all_rules

        # Récupération de tous les produits (sudo requis pour l'utilisateur public, avec contexte multi-société pour le stock)
        all_companies = request.env['res.company'].sudo().search([])
        all_products = request.env['product.template'].sudo().with_context(allowed_company_ids=all_companies.ids)
        for rule in bxgy_rules:
            all_products |= rule.product_ids.mapped('product_tmpl_id').sudo().with_context(allowed_company_ids=all_companies.ids)

        # Calcul des prix identique à la page produits (pricelist du site web)
        current_website = request.website
        pricelist = current_website.pricelist_id
        product_prices = {}
        product_stocks = {}
        for pt in all_products:
            variant = pt.sudo().product_variant_id
            if variant and pricelist:
                try:
                    price = pricelist._get_product_price(
                        variant, 1.0, currency=pricelist.currency_id
                    )
                except Exception:
                    price = pt.list_price
            else:
                price = pt.list_price
            product_prices[pt.id] = price
            # Stock calculé avec le contexte multi-société (all_products porte
            # allowed_company_ids), pour rester cohérent avec la page /produits.
            product_stocks[pt.id] = int(pt.qty_available or 0)

        values = {
            'bxgy_rules': bxgy_rules,
            'currency': current_website.currency_id,
            'has_promotions': bool(bxgy_rules),
            'product_prices': product_prices,
            'product_stocks': product_stocks,
        }
        return request.render("website_emakmed_promotion.promotions_page", values)