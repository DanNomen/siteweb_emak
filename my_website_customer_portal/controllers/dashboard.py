# -*- coding: utf-8 -*-
"""
Tableau de bord client : affiche les achats des 12 derniers mois.
"""
import json
from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import fields, http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request


class CustomerPortalDashboard(CustomerPortal):

    @http.route(['/my/dashboard'], type='http', auth='user', website=True)
    def portal_my_dashboard(self, **kw):
        """Tableau de bord : commandes des 12 derniers mois du client."""
        partner = request.env.user.partner_id

        domain = [
            ('partner_id', 'child_of', partner.id),
            ('state', 'in', ['sale', 'done']),
            ('date_order', '>=', fields.Datetime.now() - relativedelta(months=12)),
        ]
        orders = request.env['sale.order'].sudo().search(domain)

        monthly_data = defaultdict(float)
        for order in orders:
            if order.date_order:
                month_key = order.date_order.strftime('%Y-%m')
                monthly_data[month_key] += order.amount_total

        labels, data = [], []
        for i in range(11, -1, -1):
            dt = fields.Datetime.now() - relativedelta(months=i)
            month_key = dt.strftime('%Y-%m')
            labels.append(dt.strftime('%b %Y'))
            data.append(round(monthly_data.get(month_key, 0.0), 2))

        values = self._prepare_portal_layout_values()
        values.update({
            'dashboard_labels': json.dumps(labels),
            'dashboard_data': json.dumps(data),
            'page_name': 'dashboard',
        })

        return request.render("my_website_customer_portal.portal_my_dashboard", values)
