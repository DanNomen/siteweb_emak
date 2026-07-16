# -*- coding: utf-8 -*-
from odoo import http, registry, SUPERUSER_ID, api
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class WebsiteConfirmOrder(http.Controller):

    @http.route(['/confirm_order_web'], type='http', auth="public", website=True, csrf=True)
    def confirm_order(self, **kw):
        _logger.warning("=== CONFIRM_ORDER_WEB V2 ACTIF (ISOLATED CURSOR) ===")
        
        order = request.website.sale_get_order()
        if not order:
            return request.redirect('/shop')

        if order.state == 'draft':
            # Utilisation d'un NOUVEAU curseur isolé avec SUPERUSER_ID.
            # Cela permet d'écrire et de flush complètement la commande
            # indépendamment de la transaction de l'utilisateur public !
            with registry(request.env.cr.dbname).cursor() as new_cr:
                env = api.Environment(new_cr, SUPERUSER_ID, request.env.context)
                order_iso = env['sale.order'].browse(order.id)
                order_iso.write({'state': 'sent'})

        request.session['sale_last_order_id'] = order.id
        request.website.sale_reset()
        return request.redirect('/shop/confirmation')
