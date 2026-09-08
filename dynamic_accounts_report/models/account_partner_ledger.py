# -*- coding: utf-8 -*-
import io
import json
import calendar
from dateutil.relativedelta import relativedelta
import xlsxwriter
from odoo import api, fields, models
from datetime import datetime
from odoo.tools import date_utils
from .report_xlsx_utils import to_float, AMOUNT_NUM_FORMAT

class AccountPartnerLedger(models.TransientModel):
    """For creating Partner Ledger report"""
    _name = 'account.partner.ledger'
    _description = 'Partner Ledger Report'

    @api.model
    def view_report(self, option, tag):
        """
        Returns only partner totals for initial page load (NO move line details).

        `option`/`tag` are the wizard id and action display name sent by the
        frontend (see partner_ledger.js: view_report([self.wizard_id, action_title])) -
        they are NOT filter values. Real tag/category filtering only happens
        later via applyFilter(), which calls get_filter_values() directly with
        actual partner-tag ids. Forwarding `tag` (a string like "Partner Ledger")
        as `tag_ids` here used to corrupt the very first RPC call on page load
        (domain 'category_id' 'in' a string instead of a list of ids), which is
        why the page got stuck.
        """
        return self.get_filter_values(None, None, None, None, tag_ids=None, account_ids=None)

    @api.model
    def get_filter_values(self, partner_id, data_range, account, options, tag_ids=None,
                          account_ids=None, account_search=None, partner_search=None,
                          piece_search=None):
        """
        Retrieve filtered partner-related data for generating a report.
        Uses read_group for extreme performance.

        :param str account_search: Filtre texte sur le code/nom du compte.
        :param str partner_search: Filtre texte sur le nom du contact - narrows
            WHICH partners are shown (comme le filtre par étiquette ci-dessous).
        :param str piece_search: Filtre texte sur la pièce (n° de pièce/réf).
        """
        if options == {}:
            options = None
        if account == {}:
            account = None
            
        account_type_domain = []
        if options is None:
            option_domain = ['posted']
        elif 'draft' in options:
            option_domain = ['posted', 'draft']
        else:
            option_domain = ['posted']
            
        if account is None or ('Receivable' in account and 'Payable' in account):
            account_type_domain = ['liability_payable', 'asset_receivable']
        elif 'Receivable' in account:
            account_type_domain = ['asset_receivable']
        elif 'Payable' in account:
            account_type_domain = ['liability_payable']

        today = fields.Date.today()
        quarter_start, quarter_end = date_utils.get_quarter(today)
        previous_quarter_start = quarter_start - relativedelta(months=3)
        previous_quarter_end = quarter_start - relativedelta(days=1)

        # Handle partner tag filter
        if tag_ids:
            partners_with_tags = self.env['res.partner'].search([
                ('category_id', 'in', tag_ids)
            ])
            if partner_id:
                partner_id = list(set(partner_id) & set(partners_with_tags.ids))
            else:
                partner_id = partners_with_tags.ids

        # Barre de recherche "Contact" : narrows WHICH partners are shown,
        # même principe que le filtre par étiquette ci-dessus.
        if partner_search:
            partners_matching_search = self.env['res.partner'].search([
                ('name', 'ilike', partner_search)
            ])
            if partner_id:
                partner_id = list(set(partner_id) & set(partners_matching_search.ids))
            else:
                partner_id = partners_matching_search.ids

        domain = [
            ('parent_state', 'in', option_domain),
            ('display_type', 'not in', ('line_section', 'line_note')),
            ('account_type', 'in', account_type_domain)
        ]
        if partner_id:
            domain.append(('partner_id', 'in', partner_id))
        if account_ids:
            domain.append(('account_id', 'in', account_ids))
        # Barre de recherche "Compte" / "Pièce" : narrows les lignes
        # comptées par partenaire (donc les totaux affichés).
        if account_search:
            domain += ['|',
                       ('account_id.code', 'ilike', account_search),
                       ('account_id.name', 'ilike', account_search)]
        if piece_search:
            domain += ['|', '|',
                       ('move_id.name', 'ilike', piece_search),
                       ('move_id.ref', 'ilike', piece_search),
                       ('name', 'ilike', piece_search)]

        # Date filtering
        date_start = None
        if data_range:
            if data_range == 'month':
                date_start = today.replace(day=1)
                domain += [('date', '>=', date_start), ('date', '<=', today)]
            elif data_range == 'year':
                date_start = today.replace(month=1, day=1)
                domain += [('date', '>=', date_start), ('date', '<=', today)]
            elif data_range == 'quarter':
                date_start = quarter_start
                domain += [('date', '>=', date_start), ('date', '<=', quarter_end)]
            elif data_range == 'last-month':
                date_start = today.replace(day=1) - relativedelta(months=1)
                last_month_end = date_start + relativedelta(day=calendar.monthrange(date_start.year, date_start.month)[1])
                domain += [('date', '>=', date_start), ('date', '<=', last_month_end)]
            elif data_range == 'last-year':
                date_start = today.replace(month=1, day=1) - relativedelta(years=1)
                last_year_end = date_start.replace(month=12, day=31)
                domain += [('date', '>=', date_start), ('date', '<=', last_year_end)]
            elif data_range == 'last-quarter':
                date_start = previous_quarter_start
                domain += [('date', '>=', date_start), ('date', '<=', previous_quarter_end)]
            elif isinstance(data_range, dict):
                if 'start_date' in data_range and data_range['start_date']:
                    date_start = datetime.strptime(data_range['start_date'], '%Y-%m-%d').date()
                    domain.append(('date', '>=', date_start))
                if 'end_date' in data_range and data_range['end_date']:
                    end_date = datetime.strptime(data_range['end_date'], '%Y-%m-%d').date()
                    domain.append(('date', '<=', end_date))

        # 1. Main read_group for totals within date range
        groups = self.env['account.move.line'].read_group(
            domain=domain,
            fields=['partner_id', 'debit', 'credit'],
            groupby=['partner_id'],
            lazy=False
        )

        # 2. Compute initial balance
        if not date_start:
            fiscal_year = self.env['res.company'].search([]).mapped('account_opening_date')[0].strftime('%Y-%m-%d')
            date_start = datetime.strptime(fiscal_year, '%Y-%m-%d').date()

        initial_domain = [
            ('parent_state', 'in', option_domain),
            ('display_type', 'not in', ('line_section', 'line_note')),
            ('account_type', 'in', account_type_domain),
            ('date', '<', date_start)
        ]
        if partner_id:
            initial_domain.append(('partner_id', 'in', partner_id))
        if account_ids:
            initial_domain.append(('account_id', 'in', account_ids))
        if account_search:
            initial_domain += ['|',
                               ('account_id.code', 'ilike', account_search),
                               ('account_id.name', 'ilike', account_search)]
        if piece_search:
            initial_domain += ['|', '|',
                               ('move_id.name', 'ilike', piece_search),
                               ('move_id.ref', 'ilike', piece_search),
                               ('name', 'ilike', piece_search)]

        initial_groups = self.env['account.move.line'].read_group(
            domain=initial_domain,
            fields=['partner_id', 'debit', 'credit'],
            groupby=['partner_id'],
            lazy=False
        )
        
        initial_dict = {}
        for g in initial_groups:
            if g.get('partner_id'):
                pid = g['partner_id'][0]
                initial_dict[pid] = {
                    'debit': g.get('debit', 0.0),
                    'credit': g.get('credit', 0.0),
                    'balance': g.get('debit', 0.0) - g.get('credit', 0.0)
                }

        partner_totals = {}
        currency_id = self.env.company.currency_id.symbol

        # Combine results
        # We need to process partners that have either initial balance OR movements in period
        all_partner_ids = set([g['partner_id'][0] for g in groups if g.get('partner_id')])
        all_partner_ids.update(initial_dict.keys())
        
        # If no partner filter was passed, we might still have None for empty partner, filter it out
        all_partner_ids = [p for p in all_partner_ids if p]

        partner_records = self.env['res.partner'].browse(list(all_partner_ids))
        partner_name_map = {p.id: p.name for p in partner_records}

        # Partenaires triés par nom, pas dans l'ordre arbitraire d'un
        # set() (qui suivait l'ordre de hachage des ids, pas les noms).
        all_partner_ids = sorted(
            all_partner_ids,
            key=lambda pid: (partner_name_map.get(pid) or '').lower())

        group_map = {g['partner_id'][0]: g for g in groups if g.get('partner_id')}

        for pid in all_partner_ids:
            name = partner_name_map.get(pid, 'Unknown Partner')
            init_data = initial_dict.get(pid, {'debit': 0.0, 'credit': 0.0, 'balance': 0.0})
            period_data = group_map.get(pid, {'debit': 0.0, 'credit': 0.0})

            # combined_debit/credit = solde initial + mouvements de la
            # période : c'est ce qui doit être affiché sur la ligne
            # récapitulative du partenaire (pas seulement les mouvements de
            # la période, qui ignoraient le solde initial). 'balance' est le
            # solde de clôture correspondant.
            combined_debit = init_data['debit'] + period_data['debit']
            combined_credit = init_data['credit'] + period_data['credit']
            partner_totals[name] = {
                'partner_id': pid,
                'currency_id': currency_id,
                'initial_debit': init_data['debit'],
                'initial_credit': init_data['credit'],
                'initial_balance': init_data['balance'],
                'total_debit': period_data['debit'],
                'total_credit': period_data['credit'],
                'combined_debit': combined_debit,
                'combined_credit': combined_credit,
                'balance': combined_debit - combined_credit,
            }

        return {
            'partner_totals': partner_totals,
            'partners': list(partner_totals.keys())
        }

    @api.model
    def _compute_date_start(self, data_range):
        """Réplique la logique de détermination de la date de début du
        solde initial utilisée dans get_filter_values, pour les endpoints
        qui ont besoin du solde initial mais ne le calculaient pas encore
        (get_partner_lines, get_export_lines)."""
        today = fields.Date.today()
        quarter_start, quarter_end = date_utils.get_quarter(today)
        previous_quarter_start = quarter_start - relativedelta(months=3)
        date_start = None
        if data_range:
            if data_range == 'month':
                date_start = today.replace(day=1)
            elif data_range == 'year':
                date_start = today.replace(month=1, day=1)
            elif data_range == 'quarter':
                date_start = quarter_start
            elif data_range == 'last-month':
                date_start = today.replace(day=1) - relativedelta(months=1)
            elif data_range == 'last-year':
                date_start = today.replace(month=1, day=1) - relativedelta(years=1)
            elif data_range == 'last-quarter':
                date_start = previous_quarter_start
            elif isinstance(data_range, dict) and data_range.get('start_date'):
                date_start = datetime.strptime(data_range['start_date'], '%Y-%m-%d').date()
        if not date_start:
            fiscal_year = self.env['res.company'].search([]).mapped('account_opening_date')[0].strftime('%Y-%m-%d')
            date_start = datetime.strptime(fiscal_year, '%Y-%m-%d').date()
        return date_start

    @api.model
    def _compute_initial_balances(self, partner_ids, account_type_domain, option_domain, account_ids, date_start):
        """Solde initial (débit - crédit des écritures antérieures à
        date_start) par partenaire, point de départ du solde progressif."""
        initial_domain = [
            ('parent_state', 'in', option_domain),
            ('display_type', 'not in', ('line_section', 'line_note')),
            ('account_type', 'in', account_type_domain),
            ('date', '<', date_start),
            ('partner_id', 'in', partner_ids),
        ]
        if account_ids:
            initial_domain.append(('account_id', 'in', account_ids))
        groups = self.env['account.move.line'].read_group(
            domain=initial_domain, fields=['partner_id', 'debit', 'credit'],
            groupby=['partner_id'], lazy=False)
        return {
            g['partner_id'][0]: g.get('debit', 0.0) - g.get('credit', 0.0)
            for g in groups if g.get('partner_id')
        }

    @api.model
    def get_partner_lines(self, partner_id, data_range, account, options, account_ids=None):
        """
        Lazy-loads the move lines for a specific partner when expanded in the UI.
        """
        if options == {}:
            options = None
        if account == {}:
            account = None
            
        account_type_domain = []
        if options is None:
            option_domain = ['posted']
        elif 'draft' in options:
            option_domain = ['posted', 'draft']
        else:
            option_domain = ['posted']
            
        if account is None or ('Receivable' in account and 'Payable' in account):
            account_type_domain = ['liability_payable', 'asset_receivable']
        elif 'Receivable' in account:
            account_type_domain = ['asset_receivable']
        elif 'Payable' in account:
            account_type_domain = ['liability_payable']

        domain = [
            ('partner_id', '=', partner_id),
            ('parent_state', 'in', option_domain),
            ('display_type', 'not in', ('line_section', 'line_note')),
            ('account_type', 'in', account_type_domain)
        ]
        if account_ids:
            domain.append(('account_id', 'in', account_ids))

        today = fields.Date.today()
        quarter_start, quarter_end = date_utils.get_quarter(today)
        previous_quarter_start = quarter_start - relativedelta(months=3)
        previous_quarter_end = quarter_start - relativedelta(days=1)

        if data_range:
            if data_range == 'month':
                domain += [('date', '>=', today.replace(day=1)), ('date', '<=', today)]
            elif data_range == 'year':
                domain += [('date', '>=', today.replace(month=1, day=1)), ('date', '<=', today)]
            elif data_range == 'quarter':
                domain += [('date', '>=', quarter_start), ('date', '<=', quarter_end)]
            elif data_range == 'last-month':
                date_start = today.replace(day=1) - relativedelta(months=1)
                last_month_end = date_start + relativedelta(day=calendar.monthrange(date_start.year, date_start.month)[1])
                domain += [('date', '>=', date_start), ('date', '<=', last_month_end)]
            elif data_range == 'last-year':
                date_start = today.replace(month=1, day=1) - relativedelta(years=1)
                last_year_end = date_start.replace(month=12, day=31)
                domain += [('date', '>=', date_start), ('date', '<=', last_year_end)]
            elif data_range == 'last-quarter':
                domain += [('date', '>=', previous_quarter_start), ('date', '<=', previous_quarter_end)]
            elif isinstance(data_range, dict):
                if 'start_date' in data_range and data_range['start_date']:
                    start_date = datetime.strptime(data_range['start_date'], '%Y-%m-%d').date()
                    domain.append(('date', '>=', start_date))
                if 'end_date' in data_range and data_range['end_date']:
                    end_date = datetime.strptime(data_range['end_date'], '%Y-%m-%d').date()
                    domain.append(('date', '<=', end_date))

        move_lines = self.env['account.move.line'].search(domain, order='date asc', limit=500)

        # Solde progressif : solde initial + (débit - crédit) cumulés ligne
        # après ligne, dans l'ordre chronologique déjà utilisé ci-dessus.
        date_start = self._compute_date_start(data_range)
        initial_balances = self._compute_initial_balances(
            [partner_id], account_type_domain, option_domain, account_ids, date_start)
        running_balance = initial_balances.get(partner_id, 0.0)

        result = []
        for move_line in move_lines:
            move_line_data = move_line.read([
                'date', 'move_name', 'account_type', 'debit', 'credit',
                'date_maturity', 'account_id', 'journal_id', 'move_id',
                'matching_number', 'amount_currency'
            ])[0]
            if move_line.account_id:
                move_line_data['code'] = move_line.account_id.code
            if move_line.journal_id:
                move_line_data['jrnl'] = move_line.journal_id.code
            running_balance += move_line_data.get('debit', 0.0) - move_line_data.get('credit', 0.0)
            move_line_data['balance'] = running_balance
            result.append(move_line_data)

        return result

    @api.model
    def get_export_lines(self, partner_ids, data_range, account, options, account_ids=None):
        """
        Fetch move line details for MULTIPLE partners in a single query,
        grouped by partner id.

        On-screen, lines are only lazy-loaded for a single partner when its
        row is expanded (get_partner_lines), so the export never had access
        to any transaction detail - it looked empty/broken. This fetches
        everything needed for the export in one go, keyed by partner id
        (not name, since two different partners can share the same name).
        """
        if not partner_ids:
            return {}
        if options == {}:
            options = None
        if account == {}:
            account = None

        account_type_domain = []
        if options is None:
            option_domain = ['posted']
        elif 'draft' in options:
            option_domain = ['posted', 'draft']
        else:
            option_domain = ['posted']

        if account is None or ('Receivable' in account and 'Payable' in account):
            account_type_domain = ['liability_payable', 'asset_receivable']
        elif 'Receivable' in account:
            account_type_domain = ['asset_receivable']
        elif 'Payable' in account:
            account_type_domain = ['liability_payable']

        domain = [
            ('partner_id', 'in', partner_ids),
            ('parent_state', 'in', option_domain),
            ('display_type', 'not in', ('line_section', 'line_note')),
            ('account_type', 'in', account_type_domain)
        ]
        if account_ids:
            domain.append(('account_id', 'in', account_ids))

        today = fields.Date.today()
        quarter_start, quarter_end = date_utils.get_quarter(today)
        previous_quarter_start = quarter_start - relativedelta(months=3)
        previous_quarter_end = quarter_start - relativedelta(days=1)

        if data_range:
            if data_range == 'month':
                domain += [('date', '>=', today.replace(day=1)), ('date', '<=', today)]
            elif data_range == 'year':
                domain += [('date', '>=', today.replace(month=1, day=1)), ('date', '<=', today)]
            elif data_range == 'quarter':
                domain += [('date', '>=', quarter_start), ('date', '<=', quarter_end)]
            elif data_range == 'last-month':
                date_start = today.replace(day=1) - relativedelta(months=1)
                last_month_end = date_start + relativedelta(day=calendar.monthrange(date_start.year, date_start.month)[1])
                domain += [('date', '>=', date_start), ('date', '<=', last_month_end)]
            elif data_range == 'last-year':
                date_start = today.replace(month=1, day=1) - relativedelta(years=1)
                last_year_end = date_start.replace(month=12, day=31)
                domain += [('date', '>=', date_start), ('date', '<=', last_year_end)]
            elif data_range == 'last-quarter':
                domain += [('date', '>=', previous_quarter_start), ('date', '<=', previous_quarter_end)]
            elif isinstance(data_range, dict):
                if 'start_date' in data_range and data_range['start_date']:
                    start_date = datetime.strptime(data_range['start_date'], '%Y-%m-%d').date()
                    domain.append(('date', '>=', start_date))
                if 'end_date' in data_range and data_range['end_date']:
                    end_date = datetime.strptime(data_range['end_date'], '%Y-%m-%d').date()
                    domain.append(('date', '<=', end_date))

        move_lines = self.env['account.move.line'].search(domain, order='partner_id, date asc')

        # Solde progressif par partenaire : parti du solde initial de
        # chacun, puis cumulé ligne après ligne dans l'ordre chronologique
        # (lines are ordered partner_id, date asc above, so per-partner
        # blocks are processed in date order even though we key by pid
        # rather than relying on that contiguity).
        date_start = self._compute_date_start(data_range)
        running_balance = self._compute_initial_balances(
            partner_ids, account_type_domain, option_domain, account_ids, date_start)

        result = {}
        for move_line in move_lines:
            move_line_data = move_line.read([
                'date', 'move_name', 'account_type', 'debit', 'credit',
                'date_maturity', 'account_id', 'journal_id', 'move_id',
                'matching_number', 'amount_currency', 'partner_id'
            ])[0]
            if move_line.account_id:
                move_line_data['code'] = move_line.account_id.code
            if move_line.journal_id:
                move_line_data['jrnl'] = move_line.journal_id.code
            partner = move_line_data['partner_id']
            if not partner:
                continue
            pid = partner[0]
            running_balance[pid] = running_balance.get(pid, 0.0) + \
                move_line_data.get('debit', 0.0) - move_line_data.get('credit', 0.0)
            move_line_data['balance'] = running_balance[pid]
            result.setdefault(pid, []).append(move_line_data)
        return result

    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """
        Generate an Excel report based on the provided data.
        """
        data = json.loads(data)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        start_date = data['filters'].get('start_date', '')
        end_date = data['filters'].get('end_date', '')
        sheet = workbook.add_worksheet()

        # Define formats
        head = workbook.add_format({'font_size': 15, 'align': 'center', 'bold': True})
        head_highlight = workbook.add_format({'font_size': 10, 'align': 'center', 'bold': True})
        sub_heading = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10, 'border': 1, 'bg_color': '#D3D3D3',
             'border_color': 'black'})
        filter_head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10, 'border': 1, 'bg_color': '#D3D3D3',
             'border_color': 'black'})
        filter_body = workbook.add_format({'align': 'center', 'bold': True, 'font_size': 10})
        side_heading_sub = workbook.add_format(
            {'align': 'left', 'bold': True, 'font_size': 10, 'border': 1, 'border_color': 'black'})
        side_heading_sub.set_indent(1)
        txt_name = workbook.add_format({'font_size': 10, 'border': 1})
        txt_name.set_indent(2)
        # Cellules montant : vrai nombre (utilisable dans des formules
        # Excel) avec un format d'affichage numérique, au lieu d'une
        # chaîne pré-formatée ("1,234.56") qui apparaît figée/verrouillée.
        txt_name_amount = workbook.add_format(
            {'font_size': 10, 'border': 1, 'num_format': AMOUNT_NUM_FORMAT})
        txt_name_amount.set_indent(2)
        filter_head_amount = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10, 'border': 1,
             'bg_color': '#D3D3D3', 'border_color': 'black',
             'num_format': AMOUNT_NUM_FORMAT})

        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 20)
        sheet.set_column(2, 2, 15)
        sheet.set_column(3, 3, 15)

        col = 0
        sheet.write('A1:B1', report_name, head)
        sheet.write('B3:B4', 'Date Range', filter_head)
        sheet.write('B4:B4', 'Partners', filter_head)
        sheet.write('B5:B4', 'Accounts', filter_head)
        sheet.write('B6:B4', 'Options', filter_head)

        if start_date or end_date:
            sheet.merge_range('C3:G3', f"{start_date} to {end_date}", filter_body)

        if data['filters'].get('partner'):
            display_names = [p.get('display_name', 'undefined') for p in data['filters']['partner']]
            sheet.merge_range('C4:G4', ', '.join(display_names), filter_body)

        if data['filters'].get('account'):
            account_keys = list(data['filters']['account'].keys())
            sheet.merge_range('C5:G5', ', '.join(account_keys), filter_body)

        if data['filters'].get('options'):
            option_keys = list(data['filters']['options'].keys())
            sheet.merge_range('C6:G6', ', '.join(option_keys), filter_body)

        if data:
            # No report_action string-match guard here: this method is only
            # ever used for this report's own export, and gating content on
            # an exact match of the client action's xml_id (which isn't
            # always populated the same way) previously made the General
            # Ledger export silently skip all its content - "no data".
            sheet.write(8, col, ' ', sub_heading)
            sheet.write(8, col + 1, 'JNRL', sub_heading)
            sheet.write(8, col + 2, 'Account', sub_heading)
            sheet.merge_range('D9:E9', 'Ref', sub_heading)
            sheet.merge_range('F9:G9', 'Due Date', sub_heading)
            sheet.merge_range('H9:I9', 'Debit', sub_heading)
            sheet.merge_range('J9:K9', 'Credit', sub_heading)
            sheet.merge_range('L9:M9', 'Balance', sub_heading)

            row = 8
            partners = data.get('partners', []) or []
            totals = data.get('total') or {}
            # Move-line detail is fetched here, server-side, instead of
            # relying on the client to have pre-loaded it (it never had -
            # only the single partner last expanded on-screen was ever
            # loaded).
            partner_ids = [
                p.get('partner_id') for p in totals.values()
                if p.get('partner_id')
            ]
            lines_by_partner = self.get_export_lines(
                partner_ids,
                data.get('date_range'),
                data.get('account'),
                data.get('options'),
                data.get('account_ids'),
            ) if partner_ids else {}

            for partner in partners:
                row += 1
                p_data = totals.get(partner, {})
                # Ligne récapitulative du partenaire : solde initial +
                # mouvements de la période (pas seulement les mouvements),
                # comme les lignes de détail qui suivent le montrent déjà.
                initial_debit = p_data.get('initial_debit', 0.0)
                initial_credit = p_data.get('initial_credit', 0.0)
                total_debit = p_data.get('total_debit', 0.0)
                total_credit = p_data.get('total_credit', 0.0)
                combined_debit = p_data.get('combined_debit', initial_debit + total_debit)
                combined_credit = p_data.get('combined_credit', initial_credit + total_credit)
                balance = p_data.get('balance', combined_debit - combined_credit)

                sheet.write(row, col, partner, txt_name)
                sheet.write(row, col + 1, ' ', txt_name)
                sheet.write(row, col + 2, ' ', txt_name)
                sheet.merge_range(row, col + 3, row, col + 4, ' ', txt_name)
                sheet.merge_range(row, col + 5, row, col + 6, ' ', txt_name)
                sheet.merge_range(row, col + 7, row, col + 8, to_float(combined_debit), txt_name_amount)
                sheet.merge_range(row, col + 9, row, col + 10, to_float(combined_credit), txt_name_amount)
                sheet.merge_range(row, col + 11, row, col + 12, to_float(balance), txt_name_amount)

                initial_balance = p_data.get('initial_balance', 0.0)
                if initial_balance != 0:
                    row += 1

                    sheet.write(row, col, '', txt_name)
                    sheet.write(row, col + 1, ' ', txt_name)
                    sheet.write(row, col + 2, ' ', txt_name)
                    sheet.merge_range(row, col + 3, row, col + 4, 'Initial Balance', head_highlight)
                    sheet.merge_range(row, col + 5, row, col + 6, ' ', txt_name)
                    sheet.merge_range(row, col + 7, row, col + 8, to_float(initial_debit), txt_name_amount)
                    sheet.merge_range(row, col + 9, row, col + 10, to_float(initial_credit), txt_name_amount)
                    sheet.merge_range(row, col + 11, row, col + 12, to_float(initial_balance), txt_name_amount)

                # Lines
                lines = lines_by_partner.get(p_data.get('partner_id'), [])
                for rec in lines:
                    move_data = rec[0] if isinstance(rec, list) else rec
                    row += 1
                    sheet.write(row, col, str(move_data.get('date', '')), txt_name)
                    sheet.write(row, col + 1, move_data.get('jrnl', ''), txt_name)
                    sheet.write(row, col + 2, move_data.get('code', ''), txt_name)
                    sheet.merge_range(row, col + 3, row, col + 4, move_data.get('move_name', ''), txt_name)
                    sheet.merge_range(row, col + 5, row, col + 6, str(move_data.get('date_maturity', '')), txt_name)
                    sheet.merge_range(row, col + 7, row, col + 8, to_float(move_data.get('debit', 0.0)), txt_name_amount)
                    sheet.merge_range(row, col + 9, row, col + 10, to_float(move_data.get('credit', 0.0)), txt_name_amount)
                    sheet.merge_range(row, col + 11, row, col + 12, to_float(move_data.get('balance', 0.0)), txt_name_amount)

            row += 1
            grand_total_debit = data.get('grand_total', {}).get('total_debit', 0.0)
            grand_total_credit = data.get('grand_total', {}).get('total_credit', 0.0)
            grand_balance = grand_total_debit - grand_total_credit

            sheet.merge_range(row, col, row, col + 6, 'Total', filter_head)
            sheet.merge_range(row, col + 7, row, col + 8, to_float(grand_total_debit), filter_head_amount)
            sheet.merge_range(row, col + 9, row, col + 10, to_float(grand_total_credit), filter_head_amount)
            sheet.merge_range(row, col + 11, row, col + 12, to_float(grand_balance), filter_head_amount)

        workbook.close()
        output.seek(0)
        response.data = output.read()
        output.close()


class IrActionsReportPartnerLedger(models.Model):
    """Fetches Partner Ledger move-line detail server-side when the PDF is
    rendered, instead of relying on the client having pre-loaded it (it
    never had - only the single partner last expanded on-screen was ever
    loaded), which left the PDF with partner totals but no transaction
    detail at all.
    """
    _inherit = 'ir.actions.report'

    def _get_report_values(self, docids, data=None):
        if self.report_name == 'dynamic_accounts_report.partner_ledger':
            data = data or {}
            totals = data.get('total') or {}
            partner_ids = [
                p.get('partner_id') for p in totals.values()
                if p.get('partner_id')
            ]
            lines_by_partner = self.env['account.partner.ledger'].get_export_lines(
                partner_ids,
                data.get('date_range'),
                data.get('account'),
                data.get('options'),
                data.get('account_ids'),
            ) if partner_ids else {}
            # Re-key by partner name to match what the template
            # (partners/total) already indexes by.
            data['data'] = {
                name: lines_by_partner.get(p.get('partner_id'), [])
                for name, p in totals.items()
            }
        return super()._get_report_values(docids, data=data)
