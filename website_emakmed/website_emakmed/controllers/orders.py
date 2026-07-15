# -*- coding: utf-8 -*-

from odoo.http import Controller, request, route
from odoo import http


class Orders(Controller):

    @http.route('/client_orders/<string:type>', auth="public", website=True, sitemap=True)
    def client_orders(self, type='all', **kw):

        user = request.env.user

        domain = []  # exemple de filtre global

        # Si partage activé et clients autorisés
        if getattr(user, 'allow_company_orders', False):
            allowed_client_ids = user.allowed_clients.ids
            # On ajoute aussi son propre partner_id pour voir ses commandes
            partner_ids = allowed_client_ids + [user.partner_id.id]
            domain.append(('partner_id', 'in', partner_ids))
        else:
            # Sinon seulement ses propres commandes
            domain.append(('partner_id', '=', user.partner_id.id))



        if type == 'extranet':
            domain.append(('website_id', '!=', False))
            template = "website_emakmed.orders_extranet_template"

        elif type == 'inprogress':
            domain += [
                ('state', '=', 'sale'),
                ('invoice_status', '!=', 'invoiced')
            ]
            SaleOrder = request.env['sale.order'].sudo()
            if 'picking_ids' in SaleOrder._fields:
                domain.append(('picking_ids.state', '!=', 'done'))
            template = "website_emakmed.orders_inprogress_template"

        else:
            template = "website_emakmed.orders_template"

        orders = request.env['sale.order'].sudo().search(domain)
        return request.render(template, {"orders": orders})

    

    @http.route('/client_orders_detail/<int:order_id>', auth="public", website=True, sitemap=True)
    def client_orders_detail(self, order_id, **kw):

        user = request.env.user
        domain = [('id', '=', order_id)]

        if user.allow_company_orders:
            domain.append(('company_id', '=', user.company_id.id))
        else:
            domain.append(('partner_id', '=', user.partner_id.id))

        order = request.env['sale.order'].sudo().search(domain, limit=1)

        return request.render(
            'website_emakmed.orders_detail_template',
            {"order": order}
        )
