# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from datetime import date, timedelta
import babel.dates


class ClientPortalController(http.Controller):

    def _build_compte_client_values(self):
        user = request.env.user
        partner = user.partner_id
        Invoice = request.env['account.move']

        # === FACTURES POSTÉES ===
        invoices = Invoice.sudo().search([
            ('partner_id', '=', partner.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ], order='invoice_date desc')

        # === TABLEAU DE BORD PAR MOIS ===
        monthly_map = {}
        currency_symbol = request.env.company.currency_id.symbol or 'CFA'

        for inv in invoices:
            if not inv.invoice_date:
                continue
            month_key = babel.dates.format_date(
                inv.invoice_date, "MMMM yyyy", locale='fr_FR'
            ).capitalize()

            if month_key not in monthly_map:
                monthly_map[month_key] = {
                    'month': month_key,
                    'count': 0,
                    'total_ht': 0.0,
                    'total_ttc': 0.0,
                    'total_regle': 0.0,
                    'total_restant': 0.0,
                    'currency': currency_symbol,
                }
            monthly_map[month_key]['count'] += 1
            monthly_map[month_key]['total_ht'] += inv.amount_untaxed
            monthly_map[month_key]['total_ttc'] += inv.amount_total
            monthly_map[month_key]['total_regle'] += (inv.amount_total - inv.amount_residual)
            monthly_map[month_key]['total_restant'] += inv.amount_residual

        monthly_purchases = list(monthly_map.values())

        return {
            'partner': partner,
            'currency_symbol': currency_symbol,
            'monthly_purchases': monthly_purchases,
        }

    @http.route('/my-officine/compte-client', auth='user', website=True)
    def compte_client(self, **kw):
        values = self._build_compte_client_values()
        return request.render('my_website_customer_portal.client_portal_page', values)

    @http.route('/my', auth='user', website=True)
    def my_account(self, **kw):
        values = self._build_compte_client_values()
        return request.render('my_website_customer_portal.client_portal_page', values)