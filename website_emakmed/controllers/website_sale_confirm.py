# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class WebsiteConfirmOrder(http.Controller):

    @http.route(['/confirm_order_web'], type='http', auth="public", website=True, csrf=True)
    def confirm_order(self, **kw):
        order = request.website.sale_get_order()
        if not order:
            return request.redirect('/shop')

        # Passer en 'sent' pour qu'elle ne soit plus considérée comme un panier brouillon
        if order.state == 'draft':
            order.write({'state': 'sent'})

        # Sauvegarder l'ID pour la page de confirmation avant de reset le panier
        request.session['sale_last_order_id'] = order.id

        # Réinitialiser le panier après confirmation
        request.website.sale_reset()

        # Rediriger vers la page /shop
        return request.redirect('/shop/confirmation')
