# -*- coding: utf-8 -*-

from odoo import api, models
from datetime import datetime
import babel.dates


class MonthlyReport(models.AbstractModel):
    _name = 'report.website_emakmed.mensual_repport'
    _description = 'Monthly Statement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Generate report values for monthly statement PDF"""
        partner_id = docids[0] if docids else self.env.user.partner_id.id
        partner = self.env['res.partner'].browse(partner_id)
        
        # Get month and year from data if provided
        month_name = data and data.get('month_name', None)
        month = data and data.get('month', None)
        year = data and data.get('year', None)
        
        # Build domain for invoices
        domain = [
            ('partner_id', '=', partner_id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', 'not in', ['cancel','draft'])
        ]
        
        # Filter by month and year if provided (more efficient)
        if month and year:
            import calendar
            year_int = int(year)
            month_int = int(month)
            last_day = calendar.monthrange(year_int, month_int)[1]
            start_date = f"{year_int}-{month_int:02d}-01"
            end_date = f"{year_int}-{month_int:02d}-{last_day}"
            domain.extend([
                ('invoice_date', '>=', start_date),
                ('invoice_date', '<=', end_date)
            ])
        
        # Get invoices with the domain
        month_invoices = self.env['account.move'].search(domain, order='invoice_date desc')
        
        # Fallback: if only month_name is provided, filter by comparing formatted dates
        if not month and not year and month_name:
            # Get all invoices first
            all_invoices = self.env['account.move'].search([
                ('partner_id', '=', partner_id),
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state', 'not in', ['cancel','draft'])
            ], order='invoice_date desc')
            
            month_invoices = []
            for inv in all_invoices:
                if not inv.invoice_date:
                    continue
                inv_month = babel.dates.format_date(inv.invoice_date, "MMMM yyyy", locale='fr_FR').capitalize()
                if inv_month == month_name.replace('_', ' '):
                    month_invoices.append(inv)
        else:
            # Convert recordset to list for sorting
            month_invoices = list(month_invoices)
        
        # Reorder invoices: out_refund first, with each group sorted by most recent date
        month_invoices.sort(key=lambda inv: inv.invoice_date or datetime.min, reverse=True)
        month_invoices.sort(key=lambda inv: 0 if inv.move_type == 'out_refund' else 1)

        # Calculate totals (refunds minus invoices)
        total_facture_refund = sum(inv.amount_total for inv in month_invoices if inv.move_type == 'out_refund')
        total_regle_refund = sum((inv.amount_total - inv.amount_residual) for inv in month_invoices if inv.move_type == 'out_refund')
        total_restant_refund = sum(inv.amount_residual for inv in month_invoices if inv.move_type == 'out_refund')

        total_facture_invoice = sum(inv.amount_total for inv in month_invoices if inv.move_type == 'out_invoice')
        total_regle_invoice = sum((inv.amount_total - inv.amount_residual) for inv in month_invoices if inv.move_type == 'out_invoice')
        total_restant_invoice = sum(inv.amount_residual for inv in month_invoices if inv.move_type == 'out_invoice')

        total_facture = total_facture_invoice - total_facture_refund
        total_regle = total_regle_invoice - total_regle_refund
        total_restant = total_restant_invoice - total_restant_refund
        
        # Get currency symbol
        currency_symbol = month_invoices[0].currency_id.symbol if month_invoices else 'FCFA'
        
        # Generate formatted date
        generated_date = datetime.now().strftime('%d/%m/%Y à %H:%M')
        
        # Format numbers with French formatting (space as thousands separator)
        def format_number(num):
            """Format number with space as thousands separator"""
            return '{:,.2f}'.format(num).replace(',', ' ')
        
        return {
            'doc_ids': docids,
            'doc_model': 'res.partner',
            'partner': partner,
            'month_name': month_name and month_name.replace('_', ' ') or 'Tous les mois',
            'invoices': month_invoices,
            'total_facture': format_number(total_facture),
            'total_regle': format_number(total_regle),
            'total_restant': format_number(total_restant),
            'currency_symbol': currency_symbol,
            'generated_date': generated_date,
        }

