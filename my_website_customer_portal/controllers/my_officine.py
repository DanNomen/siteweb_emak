# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from collections import defaultdict
from datetime import datetime
import babel.dates 


class MyOfficine(http.Controller):

    def _get_allowed_partner_ids(self):
        """Retourne les partner_ids que l'utilisateur peut voir"""
        user = request.env.user
        partner_ids = [user.partner_id.id]  # Toujours son propre partenaire
        if getattr(user, 'allow_company_orders', False):
            partner_ids += user.allowed_clients.ids  # Ajoute les clients autorisés
        return partner_ids

    @http.route('/my_officine/invoices', auth="user", website=True)
    def my_officine_invoice(self, **kw):
        """ Affiche les factures clients de l'utilisateur connecté """
        partner_ids = self._get_allowed_partner_ids()
        invoices = request.env['account.move'].sudo().search([
            ('partner_id', 'in', partner_ids),
            ('move_type', '=', 'out_invoice'),
            ('state', '!=', 'cancel')  # on ignore les factures annulées
        ])
        values = {
            "invoices": invoices,
            "title": "Mes Factures"
        }
        return request.render('my_website_customer_portal.my_officine_invoices_template', values)

    @http.route('/my_officine/credits', auth="user", website=True)
    def my_officine_credit_notes(self, **kw):
        """ Affiche les avoirs clients de l'utilisateur connecté """
        partner_ids = self._get_allowed_partner_ids()
        credit_notes = request.env['account.move'].sudo().search([
            ('partner_id', 'in', partner_ids),
            ('move_type', '=', 'out_refund'),
            ('state', '!=', 'cancel')
        ])
        values = {
            "credit_notes": credit_notes,
            "title": "Mes Avoirs"
        }
        return request.render('my_website_customer_portal.my_officine_credit_notes_template', values)
    
    @http.route('/my_officine/statements', auth="user", website=True)
    def my_officine_statements(self, **kw):
        """ Affiche les relevés clients par mois """
        partner_ids = self._get_allowed_partner_ids()

        # Récupération de toutes les factures valides
        invoices = request.env['account.move'].sudo().search([
            ('partner_id', 'in', partner_ids),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', 'not in', ['cancel','draft'])
        ], order='invoice_date desc')

        # Grouper les factures par mois et calculer les totaux
        monthly_statements = {}
        for inv in invoices:
            if not inv.invoice_date:
                continue
            month_name = babel.dates.format_date(inv.invoice_date, "MMMM yyyy", locale='fr_FR').capitalize()
            if month_name not in monthly_statements:
                monthly_statements[month_name] = {
                    'invoices': [],
                    'total_facture': 0,
                    'total_regle': 0,
                    'total_restant': 0,
                    'total_facture_invoice': 0,
                    'total_regle_invoice': 0,
                    'total_restant_invoice': 0,
                    'total_facture_refund': 0,
                    'total_regle_refund': 0,
                    'total_restant_refund': 0
                }
            monthly_statements[month_name]['invoices'].append(inv)
            # Calcul des totaux pour chaque mois
            if inv.move_type == 'out_refund':
                monthly_statements[month_name]['total_facture_refund'] += inv.amount_total
                monthly_statements[month_name]['total_regle_refund'] += (inv.amount_total - inv.amount_residual)
                monthly_statements[month_name]['total_restant_refund'] += inv.amount_residual
            else:
                monthly_statements[month_name]['total_facture_invoice'] += inv.amount_total
                monthly_statements[month_name]['total_regle_invoice'] += (inv.amount_total - inv.amount_residual)
                monthly_statements[month_name]['total_restant_invoice'] += inv.amount_residual

        # Formater les totaux avec espaces pour les milliers
        def format_amount(amount):
            return '{:,.2f}'.format(amount).replace(',', ' ')
        
        for month_name in monthly_statements:
            statements = monthly_statements[month_name]
            # Ordonner les factures : out_refund puis out_invoice, chacune par date décroissante
            statements['invoices'].sort(key=lambda inv: inv.invoice_date or datetime.min, reverse=True)
            statements['invoices'].sort(key=lambda inv: 0 if inv.move_type == 'out_refund' else 1)

            statements['total_facture'] = statements['total_facture_invoice'] - statements['total_facture_refund']
            statements['total_regle'] = statements['total_regle_invoice'] - statements['total_regle_refund']
            statements['total_restant'] = statements['total_restant_invoice'] - statements['total_restant_refund']

            statements['total_facture'] = format_amount(statements['total_facture'])
            statements['total_regle'] = format_amount(statements['total_regle'])
            statements['total_restant'] = format_amount(statements['total_restant'])

            for helper_key in [
                'total_facture_invoice', 'total_regle_invoice', 'total_restant_invoice',
                'total_facture_refund', 'total_regle_refund', 'total_restant_refund'
            ]:
                statements.pop(helper_key, None)

        values = {
            "monthly_statements": monthly_statements,
            "title": "Mes Relevés Mensuels",
            "currency_symbol": invoices[0].currency_id.symbol if invoices else "FCFA"
        }
        return request.render('my_website_customer_portal.my_officine_statements_template', values)
    
    @http.route('/my_officine/statements/<month>', auth="user", website=True, type='http', methods=['GET'])
    def my_officine_statements_pdf(self, month=None, **kw):
        """ Génère le PDF du relevé mensuel """
        partner_ids = self._get_allowed_partner_ids()
        
        # Pour PDF, on peut filtrer sur le premier partner_id pour simplifier
        partner = request.env['res.partner'].browse(partner_ids[0])
        
        report = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'website_emakmed.mensual_repport',
            partner.id,
            data={'month_name': month}
        )[0]
        
        pdf_response = request.make_response(report)
        pdf_response.headers.set('Content-Type', 'application/pdf')
        pdf_response.headers.set('Content-Disposition', f'attachment; filename="releve_{month}.pdf"')
        return pdf_response
