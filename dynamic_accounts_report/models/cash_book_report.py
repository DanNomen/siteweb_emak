# -*- coding: utf-8 -*-
import io
import json
import calendar
from dateutil.relativedelta import relativedelta
import xlsxwriter
from datetime import datetime
from odoo.tools import date_utils
from odoo import api, fields, models
from .report_xlsx_utils import to_float, AMOUNT_NUM_FORMAT


class CashBookReport(models.TransientModel):
    """For creating Account Cash Book Report"""
    _name = 'cash.book.report'
    _description = 'Account Cash Book Report'

    def _build_domain(self, partner_id, data_range, account_list, options,
                       account_search=None, partner_search=None, piece_search=None):
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
        if account_search:
            domain += ['|', ('account_id.code', 'ilike', account_search),
                        ('account_id.name', 'ilike', account_search)]
        if partner_search:
            domain.append(('partner_id.name', 'ilike', partner_search))
        if piece_search:
            domain += ['|', '|',
                        ('move_id.name', 'ilike', piece_search),
                        ('move_id.ref', 'ilike', piece_search),
                        ('name', 'ilike', piece_search)]

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
    def get_filter_values(self, partner_id, data_range, account_list, options,
                           account_search=None, partner_search=None, piece_search=None):
        """Returns account-level totals via read_group (no line details)."""
        domain = self._build_domain(partner_id, data_range, account_list, options,
                                     account_search, partner_search, piece_search)

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

        # Trié par code de compte (plan comptable), pas dans l'ordre
        # d'apparition du read_group (qui n'est pas garanti stable/lisible).
        code_map = {a.id: a.code or '' for a in self.env['account.account'].browse(
            [v['account_id'] for v in account_totals.values()])}
        account_list_result.sort(
            key=lambda name: (code_map.get(account_totals[name]['account_id'], ''), name))

        return {
            'account_totals': account_totals,
            'accounts': account_list_result,
        }

    @api.model
    def get_account_lines(self, account_id, partner_id, data_range, account_list, options,
                           account_search=None, partner_search=None, piece_search=None):
        """Lazy-load move lines for a single account when expanded."""
        domain = self._build_domain(partner_id, data_range, account_list, options,
                                     account_search, partner_search, piece_search)
        domain.append(('account_id', '=', account_id))

        move_lines = self.env['account.move.line'].search(domain, order='date asc', limit=500)
        return move_lines.read(['date', 'journal_id', 'partner_id', 'move_name', 'debit',
                                'move_id', 'credit', 'name', 'ref'])

    @api.model
    def get_export_lines(self, account_ids, partner_id, data_range, account_list, options,
                          account_search=None, partner_search=None, piece_search=None):
        """
        Fetch move line details for MULTIPLE accounts in a single query,
        grouped by account id.

        On-screen, lines are only lazy-loaded for a single account when its
        row is expanded (get_account_lines), so the export never had access
        to any transaction detail - it looked empty/broken. This fetches
        everything needed for the export in one go, keyed by account id
        (not name, since two different accounts can share the same label).
        """
        if not account_ids:
            return {}
        domain = self._build_domain(partner_id, data_range, account_list, options,
                                     account_search, partner_search, piece_search)
        domain.append(('account_id', 'in', account_ids))

        move_lines = self.env['account.move.line'].search(domain, order='account_id, date asc')
        lines = move_lines.read(['date', 'journal_id', 'partner_id', 'move_name', 'debit',
                                 'move_id', 'credit', 'name', 'ref', 'account_id'])

        result = {}
        for line in lines:
            acc = line['account_id']
            if not acc:
                continue
            result.setdefault(acc[0], []).append(line)
        return result

    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """Generate an Excel report."""
        data = json.loads(data)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet()
        head = workbook.add_format({'font_size': 15, 'align': 'center', 'bold': True})
        sub_heading = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10, 'border': 1,
              'bg_color': '#D3D3D3', 'border_color': 'black'})
        filter_head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10, 'border': 1,
              'bg_color': '#D3D3D3', 'border_color': 'black'})
        filter_body = workbook.add_format({'align': 'center', 'bold': True, 'font_size': 10})
        txt_name = workbook.add_format({'font_size': 10, 'border': 1})
        txt_name.set_indent(2)
        # Cellules montant : vrai nombre (utilisable dans des formules Excel)
        # avec un format d'affichage identique au "{:,.2f}" utilisé avant.
        amount_format = workbook.add_format({'font_size': 10, 'border': 1, 'num_format': AMOUNT_NUM_FORMAT})
        amount_format.set_indent(2)
        sub_heading_amount = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10, 'border': 1,
              'bg_color': '#D3D3D3', 'border_color': 'black', 'num_format': AMOUNT_NUM_FORMAT})
        filter_head_amount = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10, 'border': 1,
              'bg_color': '#D3D3D3', 'border_color': 'black', 'num_format': AMOUNT_NUM_FORMAT})
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

        accounts = data.get('accounts', []) or []
        account_totals = data.get('account_totals', {}) or {}
        sheet.write(7, col, 'Account', sub_heading)
        sheet.write(7, col + 1, 'Date', sub_heading)
        sheet.write(7, col + 2, 'Reference', sub_heading)
        sheet.write(7, col + 3, 'Debit', sub_heading)
        sheet.write(7, col + 4, 'Credit', sub_heading)

        # Move-line detail is fetched here, server-side, instead of relying
        # on the client to have pre-loaded it (it never had - only the
        # single account the user last expanded on-screen was ever loaded).
        account_ids = data.get('account_ids') or [
            acc.get('account_id') for acc in account_totals.values()
            if acc.get('account_id')
        ]
        lines_by_account = self.get_export_lines(
            account_ids,
            data.get('partner_id'),
            data.get('data_range'),
            data.get('account_list'),
            data.get('options'),
            data.get('account_search'),
            data.get('partner_search'),
            data.get('piece_search'),
        ) if account_ids else {}

        row = 7
        total_debit = total_credit = 0
        for account_name in accounts:
            row += 1
            acc_data = account_totals.get(account_name, {})
            td = acc_data.get('total_debit', 0)
            tc = acc_data.get('total_credit', 0)
            total_debit += td
            total_credit += tc
            sheet.write(row, col, account_name, sub_heading)
            sheet.write(row, col + 1, '', sub_heading)
            sheet.write(row, col + 2, '', sub_heading)
            sheet.write_number(row, col + 3, to_float(td), sub_heading_amount)
            sheet.write_number(row, col + 4, to_float(tc), sub_heading_amount)

            for line in lines_by_account.get(acc_data.get('account_id'), []):
                row += 1
                sheet.write(row, col, '', txt_name)
                sheet.write(row, col + 1, str(line.get('date', '')), txt_name)
                sheet.write(row, col + 2, line.get('move_name', ''), txt_name)
                sheet.write_number(row, col + 3, to_float(line.get('debit', 0)), amount_format)
                sheet.write_number(row, col + 4, to_float(line.get('credit', 0)), amount_format)

        row += 1
        sheet.write(row, col, 'Total', filter_head)
        sheet.write(row, col + 1, '', filter_head)
        sheet.write(row, col + 2, '', filter_head)
        sheet.write_number(row, col + 3, to_float(total_debit), filter_head_amount)
        sheet.write_number(row, col + 4, to_float(total_credit), filter_head_amount)

        workbook.close()
        output.seek(0)
        response.data = output.read()
        output.close()


class ReportCashBook(models.AbstractModel):
    """Contexte de rendu du PDF Cash Book.

    Odoo n'appelle `_get_report_values` que sur un modèle nommé
    'report.<module>.<report_name>' (voir
    odoo/addons/base/models/ir_actions_report.py,
    _get_rendering_context) - jamais sur 'ir.actions.report' lui-même.
    La version précédente de ce correctif déclarait la surcharge sur
    'ir.actions.report' (`_inherit`), que le moteur de rendu n'invoque
    pas : les lignes de détail n'arrivaient donc jamais au template et
    `data` restait absent du contexte.

    Les écritures ne sont chargées à l'écran que pour le compte déplié
    (get_account_lines) : le serveur les récupère lui-même ici, à partir
    des seuls totaux par compte (qui portent déjà chaque account_id) et
    des filtres, sans les faire transiter par le payload du client.
    """
    _name = 'report.dynamic_accounts_report.cash_book'
    _description = 'Cash Book Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        account_totals = data.get('account_totals') or data.get('total') or {}
        filters = data.get('filters') or {}
        filters.setdefault('start_date', None)
        filters.setdefault('end_date', None)
        filters.setdefault('partner', [])
        filters.setdefault('account', [])
        filters.setdefault('options', {})
        account_ids = data.get('account_ids') or [
            acc.get('account_id') for acc in account_totals.values()
            if acc.get('account_id')
        ]
        lines_by_account = self.env['cash.book.report'].get_export_lines(
            account_ids,
            data.get('partner_id'),
            data.get('data_range'),
            data.get('account_list'),
            data.get('options'),
            data.get('account_search'),
            data.get('partner_search'),
            data.get('piece_search'),
        ) if account_ids else {}
        # Re-key by account name to match what the template
        # (move_lines/total) already indexes by.
        lines_by_name = {
            name: lines_by_account.get(acc.get('account_id'), [])
            for name, acc in account_totals.items()
        }
        return {
            'doc_ids': docids,
            'doc_model': 'cash.book.report',
            'docs': self.env['cash.book.report'].browse(docids or []),
            'report_name': data.get('report_name') or data.get('title') or '',
            'move_lines': data.get('move_lines') or [],
            'total': account_totals,
            'grand_total': data.get('grand_total') or {},
            'filters': filters,
            'data': lines_by_name,
        }
