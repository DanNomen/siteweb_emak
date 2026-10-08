# -*- coding: utf-8 -*-

import logging
import json
from odoo import http
from odoo.http import request
from collections import defaultdict
from datetime import datetime
import babel.dates
from odoo.addons.web.controllers.report import ReportController

_logger = logging.getLogger(__name__)


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
        return request.render('website_emakmed.my_officine_invoices_template', values)

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
        return request.render('website_emakmed.my_officine_credit_notes_template', values)
    
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
        return request.render('website_emakmed.my_officine_statements_template', values)
    
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


class CustomReportController(ReportController):

    @staticmethod
    def _is_invoice_allowed(user, invoice):
        if not invoice or not invoice.exists():
            return False
        user_partner = user.partner_id
        user_commercial = user_partner.commercial_partner_id or user_partner
        
        inv_partner = invoice.partner_id
        inv_commercial = inv_partner.commercial_partner_id or inv_partner
        
        # 1. Direct or commercial partner hierarchy match
        if inv_commercial == user_commercial or inv_partner == user_partner or inv_partner in user_commercial.child_ids:
            return True
            
        # 2. Check if user's partner is a follower / message partner on invoice
        if user_partner in invoice.message_partner_ids:
            return True
            
        # 3. Check allowed_clients (for company/multi-client portal users)
        if getattr(user, 'allow_company_orders', False) and getattr(user, 'allowed_clients', False):
            allowed_partners = user.allowed_clients
            allowed_commercials = allowed_partners.mapped('commercial_partner_id') | allowed_partners
            allowed_all = allowed_commercials | allowed_commercials.mapped('child_ids')
            if inv_partner in allowed_all or inv_commercial in allowed_commercials:
                return True
                
        return False

    @http.route([
        '/report/<converter>/<reportname>',
        '/report/<converter>/<reportname>/<docids>',
    ], type='http', auth='user', website=True, readonly=True)
    def report_routes(self, reportname, docids=None, converter=None, **data):
        user = request.env.user

        # Intercept invoice reports for non-internal users (e.g. portal / website users)
        if not user.has_group('base.group_user') and docids:
            try:
                ir_report = request.env['ir.actions.report'].sudo()._get_report_from_name(reportname)
                is_invoice_rep = (ir_report and ir_report.model == 'account.move') or ('invoice' in reportname)
                if is_invoice_rep:
                    parsed_docids = [int(i) for i in docids.split(',') if i.isdigit()]
                    if parsed_docids:
                        invoices = request.env['account.move'].sudo().browse(parsed_docids)
                        if invoices and all(self._is_invoice_allowed(user, inv) for inv in invoices):
                            context = dict(request.env.context)
                            if data.get('options'):
                                data.update(json.loads(data.pop('options')))
                            if data.get('context'):
                                data['context'] = json.loads(data['context'])
                                context.update(data['context'])

                            report_sudo = ir_report.sudo() if ir_report else request.env['ir.actions.report'].sudo()._get_report_from_name(reportname).sudo()

                            if converter == 'pdf':
                                pdf = report_sudo.with_context(context)._render_qweb_pdf(reportname, parsed_docids, data=data)[0]
                                pdfhttpheaders = [('Content-Type', 'application/pdf'), ('Content-Length', len(pdf))]
                                return request.make_response(pdf, headers=pdfhttpheaders)
                            elif converter == 'html':
                                html = report_sudo.with_context(context)._render_qweb_html(reportname, parsed_docids, data=data)[0]
                                return request.make_response(html)
            except Exception as e:
                _logger.error("Error generating portal invoice report %s for docids %s: %s", reportname, docids, e)

        return super().report_routes(reportname, docids=docids, converter=converter, **data)
