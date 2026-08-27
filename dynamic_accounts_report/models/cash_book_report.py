# -*- coding: utf-8 -*-
import io
import json
import calendar
from dateutil.relativedelta import relativedelta
import xlsxwriter
from datetime import datetime
from odoo.tools import date_utils
from odoo import api, fields, models


class CashBookReport(models.TransientModel):
    """For creating Account Cash Book Report"""
    _name = 'cash.book.report'
    _description = 'Account Cash Book Report'

    def _build_domain(self, partner_id, data_range, account_list, options):
        """Build search domain based on filters."""
        today = fields.Date.today()
        quarter_start, quarter_end = date_utils.get_quarter(today)
        previous_quarter_start = quarter_start - relativedelta(months=3)
        previous_quarter_end = quarter_start - relativedelta(days=1)
        
        if options == {} or options is None:
            option_domain = ['posted']
        elif 'draft' in options:
            option_domain = ['posted', 'draft']
        else:
            option_domain = ['posted']
        
        journals = self.env['account.journal'].search([('type', '=', 'cash')])
        domain = [('parent_state', 'in', option_domain), ('journal_id', 'in', journals.ids)]
        
        if partner_id:
            domain.append(('partner_id', 'in', partner_id))
        if account_list:
            domain.append(('account_id', 'in', account_list))
        
        if data_range:
            if data_range == 'month':
                domain += [('date', '>=', today.replace(day=1)), ('date', '<=', today)]
            elif data_range == 'year':
                domain += [('date', '>=', today.replace(month=1, day=1)), ('date', '<=', today)]
            elif data_range == 'quarter':
                domain += [('date', '>=', quarter_start), ('date', '<=', quarter_end)]
            elif data_range == 'last-month':
                last_start = today.replace(day=1) - relativedelta(months=1)
                last_end = last_start + relativedelta(day=calendar.monthrange(last_start.year, last_start.month)[1])
                domain += [('date', '>=', last_start), ('date', '<=', last_end)]
            elif data_range == 'last-year':
                last_start = today.replace(month=1, day=1) - relativedelta(years=1)
                last_end = last_start.replace(month=12, day=31)
                domain += [('date', '>=', last_start), ('date', '<=', last_end)]
            elif data_range == 'last-quarter':
                domain += [('date', '>=', previous_quarter_start), ('date', '<=', previous_quarter_end)]
            elif isinstance(data_range, dict):
                if data_range.get('start_date'):
                    domain.append(('date', '>=', datetime.strptime(data_range['start_date'], '%Y-%m-%d').date()))
                if data_range.get('end_date'):
                    domain.append(('date', '<=', datetime.strptime(data_range['end_date'], '%Y-%m-%d').date()))
        
        return domain

    @api.model
    def view_report(self):
        """Returns account totals only (fast), no detail lines."""
        return self.get_filter_values(None, None, None, None)

    @api.model
    def get_filter_values(self, partner_id, data_range, account_list, options):
        """Returns account-level totals via read_group (no line details)."""
        domain = self._build_domain(partner_id, data_range, account_list, options)
        
        groups = self.env['account.move.line'].read_group(
            domain=domain,
            fields=['account_id', 'debit', 'credit'],
            groupby=['account_id'],
            lazy=False
        )
        
        currency_id = self.env.company.currency_id.symbol
        account_totals = {}
        account_list_result = []
        
        for group in groups:
            if not group.get('account_id'):
                continue
            acc_id = group['account_id'][0]
            acc_name = group['account_id'][1]
            account_totals[acc_name] = {
                'account_id': acc_id,
                'total_debit': round(group.get('debit', 0.0), 2),
                'total_credit': round(group.get('credit', 0.0), 2),
                'currency_id': currency_id,
            }
            account_list_result.append(acc_name)
        
        return {
            'account_totals': account_totals,
            'accounts': account_list_result,
        }

    @api.model
    def get_account_lines(self, account_id, partner_id, data_range, account_list, options):
        """Lazy-load move lines for a single account when expanded."""
        domain = self._build_domain(partner_id, data_range, account_list, options)
        domain.append(('account_id', '=', account_id))
        
        move_lines = self.env['account.move.line'].search(domain, order='date asc', limit=500)
        return move_lines.read(['date', 'journal_id', 'partner_id', 'move_name', 'debit',
                                'move_id', 'credit', 'name', 'ref'])

    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """Generate an Excel report."""
        data = json.loads(data)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet()
        head = workbook.add_format({'font_size': 15, 'align': 'center', 'bold': True})
        sub_heading = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px', 'border': 1,
              'bg_color': '#D3D3D3', 'border_color': 'black'})
        filter_head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px', 'border': 1,
              'bg_color': '#D3D3D3', 'border_color': 'black'})
        filter_body = workbook.add_format({'align': 'center', 'bold': True, 'font_size': '10px'})
        txt_name = workbook.add_format({'font_size': '10px', 'border': 1})
        txt_name.set_indent(2)
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 20)
        sheet.set_column(2, 2, 30)

        col = 0
        sheet.write('A1:B1', report_name, head)
        filters = data.get('filters', {})
        start_date = filters.get('start_date', '')
        end_date = filters.get('end_date', '')
        sheet.write('B3:B4', 'Date Range', filter_head)
        if start_date or end_date:
            sheet.merge_range('C3:G3', f"{start_date} to {end_date}", filter_body)

        def fmt(v):
            return "{:,.2f}".format(float(v or 0))

        accounts = data.get('accounts', []) or []
        sheet.write(7, col, 'Account', sub_heading)
        sheet.write(7, col + 1, 'Date', sub_heading)
        sheet.write(7, col + 2, 'Reference', sub_heading)
        sheet.write(7, col + 3, 'Debit', sub_heading)
        sheet.write(7, col + 4, 'Credit', sub_heading)
        
        row = 7
        total_debit = total_credit = 0
        for account_name in accounts:
            row += 1
            acc_data = data.get('account_totals', {}).get(account_name, {})
            td = acc_data.get('total_debit', 0)
            tc = acc_data.get('total_credit', 0)
            total_debit += td
            total_credit += tc
            sheet.write(row, col, account_name, sub_heading)
            sheet.write(row, col + 1, '', sub_heading)
            sheet.write(row, col + 2, '', sub_heading)
            sheet.write(row, col + 3, fmt(td), sub_heading)
            sheet.write(row, col + 4, fmt(tc), sub_heading)
            
            # lines if exported
            for line in data.get('data', {}).get(account_name, []):
                row += 1
                sheet.write(row, col, '', txt_name)
                sheet.write(row, col + 1, str(line.get('date', '')), txt_name)
                sheet.write(row, col + 2, line.get('move_name', ''), txt_name)
                sheet.write(row, col + 3, fmt(line.get('debit', 0)), txt_name)
                sheet.write(row, col + 4, fmt(line.get('credit', 0)), txt_name)
        
        row += 1
        sheet.write(row, col, 'Total', filter_head)
        sheet.write(row, col + 1, '', filter_head)
        sheet.write(row, col + 2, '', filter_head)
        sheet.write(row, col + 3, fmt(total_debit), filter_head)
        sheet.write(row, col + 4, fmt(total_credit), filter_head)

        workbook.close()
        output.seek(0)
        response.data = output.read()
        output.close()
