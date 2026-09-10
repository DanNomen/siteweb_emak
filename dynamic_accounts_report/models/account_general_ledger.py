# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Bhagyadev KP (<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
import io
import json
import calendar
from dateutil.relativedelta import relativedelta
import xlsxwriter
from odoo import api, fields, models
from datetime import datetime
from odoo.tools import date_utils
from .report_xlsx_utils import to_float, AMOUNT_NUM_FORMAT


class AccountGeneralLedger(models.TransientModel):
    """For creating General Ledger report"""
    _name = 'account.general.ledger'
    _description = 'General Ledger Report'

    @api.model
    def disable_duplicate_menus(self):
        """
        Safely disable duplicate accounting menus from other third-party modules
        if they are installed. This avoids XML ParseErrors when a module is not installed.
        """
        xml_ids_to_disable = [
            'accounting_pdf_reports.menu_finance_legal_statement',
            'accounting_pdf_reports.menu_finance_partner_reports',
            'accounting_pdf_reports.menu_finance_audit_reports',
            'base_accounting_kit.account_reports_generic_statements',
            'base_accounting_kit.account_reports_daily_reports',
            'base_accounting_kit.account_reports_partner',
            'base_accounting_kit.account_reports_audit',
            'om_account_daily_reports.menu_finance_daily_reports'
        ]
        for xml_id in xml_ids_to_disable:
            menu = self.env.ref(xml_id, raise_if_not_found=False)
            if menu:
                menu.active = False

    @api.model
    def view_report(self, option, tag):
        """
        Returns only account totals for initial page load (NO move line details).
        Move line details are loaded on demand via get_account_lines().
        This prevents browser crashes on large datasets.
        """
        account_dict = {}
        account_totals = {}
        currency_id = self.env.company.currency_id.symbol

        # Use read_group for a single, fast aggregated SQL query instead of
        # loading all move lines into Python memory
        domain = [('parent_state', '=', 'posted'),
                  ('display_type', 'not in', ('line_section', 'line_note'))]

        groups = self.env['account.move.line'].read_group(
            domain=domain,
            fields=['account_id', 'debit:sum', 'credit:sum'],
            groupby=['account_id'],
            orderby='account_id asc',
        )

        account_dict['journal_ids'] = self.env['account.journal'].search_read(
            [], ['name'])
        account_dict['analytic_ids'] = self.env[
            'account.analytic.account'].search_read([], ['name'])

        # Comptes triés par code (plan comptable), pas dans l'ordre
        # d'apparition du groupby (qui suit l'id interne du compte).
        group_account_ids = [g['account_id'][0] for g in groups if g.get('account_id')]
        account_code_map = {}
        if group_account_ids:
            account_recs = self.env['account.account'].search_read(
                [('id', 'in', group_account_ids)], ['code'])
            account_code_map = {a['id']: a['code'] or '' for a in account_recs}
        groups.sort(key=lambda g: account_code_map.get(g['account_id'][0], '')
                    if g.get('account_id') else '')

        for group in groups:
            if not group['account_id']:
                continue
            account_id, account_name = group['account_id']
            total_debit = round(group['debit'] or 0, 2)
            total_credit = round(group['credit'] or 0, 2)
            # Pas de filtre de dates ici (tout l'historique est déjà
            # inclus) : pas de solde initial séparé à calculer, mais on
            # renvoie quand même combined_debit/combined_credit/balance
            # (identiques à total_debit/total_credit ici) pour que l'écran,
            # l'export et le PDF - qui lisent ces clés sans .get() - ne
            # plantent pas quand on imprime avant d'avoir appliqué un
            # filtre (KeyError: 'combined_debit').
            account_totals[account_name] = {
                'total_debit': total_debit,
                'total_credit': total_credit,
                'currency_id': currency_id,
                'account_id': account_id,
                'line_count': group['account_id_count'],
                'initial_debit': 0.0,
                'initial_credit': 0.0,
                'initial_balance': 0.0,
                'combined_debit': total_debit,
                'combined_credit': total_credit,
                'balance': total_debit - total_credit,
            }

        account_dict['account_totals'] = account_totals
        return account_dict

    @api.model
    def _compute_date_start(self, date_range):
        """Détermine la date à partir de laquelle les écritures antérieures
        constituent le solde initial d'un compte - même logique que le
        filtre de dates ci-dessous, mais retournant juste la borne de
        début (ou la date d'ouverture de l'exercice si aucun filtre de
        date n'a de borne de début)."""
        today = fields.Date.today()
        quarter_start, quarter_end = date_utils.get_quarter(today)
        previous_quarter_start = quarter_start - relativedelta(months=3)
        date_start = None
        if date_range:
            if date_range == 'month':
                date_start = today.replace(day=1)
            elif date_range == 'year':
                date_start = today.replace(month=1, day=1)
            elif date_range == 'quarter':
                date_start = quarter_start
            elif date_range == 'last-month':
                date_start = today.replace(day=1) - relativedelta(months=1)
            elif date_range == 'last-year':
                date_start = today.replace(month=1, day=1) - relativedelta(years=1)
            elif date_range == 'last-quarter':
                date_start = previous_quarter_start
            elif isinstance(date_range, dict) and date_range.get('start_date'):
                date_start = datetime.strptime(date_range['start_date'], '%Y-%m-%d').date()
        if not date_start:
            fiscal_year = self.env['res.company'].search([]).mapped('account_opening_date')[0].strftime('%Y-%m-%d')
            date_start = datetime.strptime(fiscal_year, '%Y-%m-%d').date()
        return date_start

    @api.model
    def _compute_initial_balances(self, account_ids, journal_ids, options, analytic, method, date_start):
        """Solde initial (débit - crédit des écritures antérieures à
        date_start) par compte, point de départ du solde progressif -
        mêmes filtres (journal/options/analytique/méthode de caisse) que
        la période elle-même, sauf la date."""
        domain = self._build_lines_domain(journal_ids, None, options, analytic, method)
        domain += [('date', '<', date_start), ('account_id', 'in', account_ids)]
        groups = self.env['account.move.line'].read_group(
            domain=domain, fields=['account_id', 'debit', 'credit'],
            groupby=['account_id'], lazy=False)
        return {
            g['account_id'][0]: g.get('debit', 0.0) - g.get('credit', 0.0)
            for g in groups if g.get('account_id')
        }

    def _build_lines_domain(self, journal_ids=None, date_range=None,
                            options=None, analytic=None, method=None):
        """Shared filter domain (everything except the account_id part) used
        by both get_account_lines (single account, lazy-load on expand) and
        get_export_lines (multiple accounts at once, for XLSX/PDF export).
        """
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

        domain = [
            ('parent_state', 'in', option_domain),
            ('display_type', 'not in', ('line_section', 'line_note')),
        ]

        if journal_ids:
            domain += [('journal_id', 'in', journal_ids)]

        if method and 'cash' in (method or {}):
            domain += [('journal_id', 'in',
                        self.env.company.tax_cash_basis_journal_id.ids)]

        if analytic:
            analytic_line = self.env['account.analytic.line'].search(
                [('account_id', 'in', analytic)]).mapped('id')
            domain += [('analytic_line_ids', 'in', analytic_line)]

        if date_range:
            if date_range == 'month':
                domain += [('date', '>=', today.replace(day=1)),
                           ('date', '<=', today)]
            elif date_range == 'year':
                domain += [('date', '>=', today.replace(month=1, day=1)),
                           ('date', '<=', today)]
            elif date_range == 'quarter':
                domain += [('date', '>=', quarter_start),
                           ('date', '<=', quarter_end)]
            elif date_range == 'last-month':
                last_month_start = today.replace(day=1) - relativedelta(months=1)
                last_month_end = last_month_start + relativedelta(
                    day=calendar.monthrange(last_month_start.year,
                                            last_month_start.month)[1])
                domain += [('date', '>=', last_month_start),
                           ('date', '<=', last_month_end)]
            elif date_range == 'last-year':
                last_year_start = today.replace(month=1, day=1) - relativedelta(years=1)
                last_year_end = last_year_start.replace(month=12, day=31)
                domain += [('date', '>=', last_year_start),
                           ('date', '<=', last_year_end)]
            elif date_range == 'last-quarter':
                domain += [('date', '>=', previous_quarter_start),
                           ('date', '<=', previous_quarter_end)]
            elif isinstance(date_range, dict):
                if 'start_date' in date_range and 'end_date' in date_range:
                    start_date = datetime.strptime(date_range['start_date'], '%Y-%m-%d').date()
                    end_date = datetime.strptime(date_range['end_date'], '%Y-%m-%d').date()
                    domain += [('date', '>=', start_date), ('date', '<=', end_date)]
                elif 'start_date' in date_range:
                    start_date = datetime.strptime(date_range['start_date'], '%Y-%m-%d').date()
                    domain += [('date', '>=', start_date)]
                elif 'end_date' in date_range:
                    end_date = datetime.strptime(date_range['end_date'], '%Y-%m-%d').date()
                    domain += [('date', '<=', end_date)]

        return domain

    @api.model
    def get_account_lines(self, account_id, journal_ids=None, date_range=None,
                          options=None, analytic=None, method=None):
        """
        Lazy-load move line details for a single account.
        Called when the user expands an account row in the UI.
        """
        domain = self._build_lines_domain(journal_ids, date_range, options, analytic, method)
        domain.append(('account_id', '=', account_id))

        move_lines = self.env['account.move.line'].search(domain, order='date asc', limit=500)
        result = move_lines.read(
            ['date', 'name', 'move_name', 'debit', 'credit',
             'partner_id', 'account_id', 'journal_id', 'move_id'])

        # Solde progressif : solde initial (écritures antérieures au
        # filtre de dates) + (débit - crédit) cumulés ligne après ligne.
        date_start = self._compute_date_start(date_range)
        initial_balances = self._compute_initial_balances(
            [account_id], journal_ids, options, analytic, method, date_start)
        running_balance = initial_balances.get(account_id, 0.0)
        for move_line_data in result:
            running_balance += move_line_data.get('debit', 0.0) - move_line_data.get('credit', 0.0)
            move_line_data['balance'] = running_balance

        return result

    @api.model
    def get_export_lines(self, account_ids, journal_ids=None, date_range=None,
                         options=None, analytic=None, method=None):
        """
        Fetch move line details for MULTIPLE accounts in a single query,
        grouped by account id.

        Needed for XLSX/PDF export: the on-screen report only lazy-loads
        lines for a single account when the user expands its row
        (get_account_lines), so account_data/account_total never contain
        every account's lines - exporting straight from that state produced
        a file with account totals but NO transaction detail (looking
        empty/broken to the user). This fetches everything needed for the
        export in one go instead of looping get_account_lines per account.

        Grouped by id, not by display name: two different accounts can
        share the same name (e.g. same label, different account codes),
        which would silently merge or drop their lines under a single
        string key.
        """
        if not account_ids:
            return {}
        domain = self._build_lines_domain(journal_ids, date_range, options, analytic, method)
        domain.append(('account_id', 'in', account_ids))

        move_lines = self.env['account.move.line'].search(domain, order='account_id, date asc')
        lines = move_lines.read(
            ['date', 'name', 'move_name', 'debit', 'credit',
             'partner_id', 'account_id', 'journal_id', 'move_id'])

        # Solde progressif par compte : parti du solde initial de chacun,
        # puis cumulé ligne après ligne dans l'ordre chronologique (lines
        # is ordered account_id, date asc above).
        date_start = self._compute_date_start(date_range)
        running_balance = self._compute_initial_balances(
            account_ids, journal_ids, options, analytic, method, date_start)

        result = {}
        for line in lines:
            acc = line['account_id']
            if not acc:
                continue
            acc_id = acc[0]
            running_balance[acc_id] = running_balance.get(acc_id, 0.0) + \
                line.get('debit', 0.0) - line.get('credit', 0.0)
            line['balance'] = running_balance[acc_id]
            result.setdefault(acc_id, []).append(line)
        return result

    @api.model
    def get_filter_values(self, journal_id, date_range, options, analytic,
                          method, account_search=None, partner_search=None,
                          piece_search=None):
        """
        Returns filtered account totals (NO move line details).
        Uses a single read_group SQL query for performance.

        :param str account_search: Filtre texte sur le code/nom du compte.
        :param str partner_search: Filtre texte sur le nom du contact.
        :param str piece_search: Filtre texte sur la pièce (n° de pièce/réf).
        """
        account_dict = {}
        account_totals = {}
        today = fields.Date.today()
        quarter_start, quarter_end = date_utils.get_quarter(today)
        previous_quarter_start = quarter_start - relativedelta(months=3)
        previous_quarter_end = quarter_start - relativedelta(days=1)
        if options == {}:
            options = None
        if options is None:
            option_domain = ['posted']
        elif 'draft' in options:
            option_domain = ['posted', 'draft']
        else:
            option_domain = ['posted']
        domain = [('parent_state', 'in', option_domain),
                  ('display_type', 'not in', ('line_section', 'line_note'))]
        if journal_id:
            domain += [('journal_id', 'in', journal_id)]
        if method == {}:
            method = None
        if method is not None and 'cash' in method:
            domain += [('journal_id', 'in',
                        self.env.company.tax_cash_basis_journal_id.ids)]
        if analytic:
            analytic_line = self.env['account.analytic.line'].search(
                [('account_id', 'in', analytic)]).mapped('id')
            domain += [('analytic_line_ids', 'in', analytic_line)]
        if date_range:
            if date_range == 'month':
                domain += [('date', '>=', today.replace(day=1)),
                           ('date', '<=', today)]
            elif date_range == 'year':
                domain += [('date', '>=', today.replace(month=1, day=1)),
                           ('date', '<=', today)]
            elif date_range == 'quarter':
                domain += [('date', '>=', quarter_start),
                           ('date', '<=', quarter_end)]
            elif date_range == 'last-month':
                last_month_start = today.replace(day=1) - relativedelta(months=1)
                last_month_end = last_month_start + relativedelta(
                    day=calendar.monthrange(last_month_start.year,
                                            last_month_start.month)[1])
                domain += [('date', '>=', last_month_start),
                           ('date', '<=', last_month_end)]
            elif date_range == 'last-year':
                last_year_start = today.replace(month=1, day=1) - relativedelta(years=1)
                last_year_end = last_year_start.replace(month=12, day=31)
                domain += [('date', '>=', last_year_start),
                           ('date', '<=', last_year_end)]
            elif date_range == 'last-quarter':
                domain += [('date', '>=', previous_quarter_start),
                           ('date', '<=', previous_quarter_end)]
            elif isinstance(date_range, dict):
                if 'start_date' in date_range and 'end_date' in date_range:
                    start_date = datetime.strptime(date_range['start_date'], '%Y-%m-%d').date()
                    end_date = datetime.strptime(date_range['end_date'], '%Y-%m-%d').date()
                    domain += [('date', '>=', start_date), ('date', '<=', end_date)]
                elif 'start_date' in date_range:
                    start_date = datetime.strptime(date_range['start_date'], '%Y-%m-%d').date()
                    domain += [('date', '>=', start_date)]
                elif 'end_date' in date_range:
                    end_date = datetime.strptime(date_range['end_date'], '%Y-%m-%d').date()
                    domain += [('date', '<=', end_date)]

        # Barre de recherche : compte (code/nom), contact, pièce. Ces
        # clauses réduisent directement le domaine des lignes d'écriture
        # utilisé par le read_group ci-dessous, donc elles narrows à la
        # fois les comptes affichés (account_search) et les totaux/comptes
        # visibles (partner_search / piece_search).
        if account_search:
            domain += ['|',
                       ('account_id.code', 'ilike', account_search),
                       ('account_id.name', 'ilike', account_search)]
        if partner_search:
            domain.append(('partner_id.name', 'ilike', partner_search))
        if piece_search:
            domain += ['|', '|',
                       ('move_id.name', 'ilike', piece_search),
                       ('move_id.ref', 'ilike', piece_search),
                       ('name', 'ilike', piece_search)]

        currency_id = self.env.company.currency_id.symbol
        groups = self.env['account.move.line'].read_group(
            domain=domain,
            fields=['account_id', 'debit:sum', 'credit:sum'],
            groupby=['account_id'],
            orderby='account_id asc',
        )
        account_dict['journal_ids'] = self.env['account.journal'].search_read([], ['name'])
        account_dict['analytic_ids'] = self.env['account.analytic.account'].search_read([], ['name'])

        # Comptes triés par code (plan comptable), pas dans l'ordre
        # d'apparition du groupby (qui suit l'id interne du compte).
        group_account_ids = [g['account_id'][0] for g in groups if g.get('account_id')]
        account_code_map = {}
        if group_account_ids:
            account_recs = self.env['account.account'].search_read(
                [('id', 'in', group_account_ids)], ['code'])
            account_code_map = {a['id']: a['code'] or '' for a in account_recs}
        groups.sort(key=lambda g: account_code_map.get(g['account_id'][0], '')
                    if g.get('account_id') else '')

        # Solde initial : uniquement pertinent quand un filtre de dates est
        # actif (sinon la période couvre déjà tout l'historique, donc
        # total_debit/total_credit sont déjà le solde complet - pas besoin
        # de solde initial séparé). C'est ça qui manquait pour que le solde
        # de fin de janvier redevienne le solde de départ de février.
        initial_balances = {}
        if date_range and group_account_ids:
            date_start = self._compute_date_start(date_range)
            initial_balances = self._compute_initial_balances(
                group_account_ids, journal_id, options, analytic, method, date_start)

        for group in groups:
            if not group['account_id']:
                continue
            account_id, account_name = group['account_id']
            total_debit = round(group['debit'] or 0, 2)
            total_credit = round(group['credit'] or 0, 2)
            # Un solde s'affiche du côté débit OU crédit, jamais les deux
            # (convention comptable), comme pour le reste du module.
            initial_balance = initial_balances.get(account_id, 0.0)
            if initial_balance > 0:
                initial_debit, initial_credit = initial_balance, 0.0
            else:
                initial_debit, initial_credit = 0.0, -initial_balance
            combined_debit = total_debit + initial_debit
            combined_credit = total_credit + initial_credit
            account_totals[account_name] = {
                'total_debit': total_debit,
                'total_credit': total_credit,
                'currency_id': currency_id,
                'account_id': account_id,
                'line_count': group['account_id_count'],
                'initial_debit': initial_debit,
                'initial_credit': initial_credit,
                'initial_balance': initial_balance,
                'combined_debit': combined_debit,
                'combined_credit': combined_credit,
                'balance': combined_debit - combined_credit,
            }

        account_dict['account_totals'] = account_totals
        return account_dict

    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """
        Generate an XLSX report based on the provided data and write it to the
        response stream.

        :param data: The data used to generate the report.
        :type data: str (JSON format)

        :param response: The response object to write the generated report to.
        :type response: werkzeug.wrappers.Response

        :param report_name: The name of the report.
        :type report_name: str
        """
        data = json.loads(data)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        start_date = data['filters']['start_date'] if \
            data['filters']['start_date'] else ''
        end_date = data['filters']['end_date'] if \
            data['filters']['end_date'] else ''
        sheet = workbook.add_worksheet()
        # font_size must be a plain point size (int/float), not a CSS-style
        # '10px' string - xlsxwriter writes it verbatim into styles.xml as
        # <sz val="10px"/>, which is invalid and made Excel discard the
        # whole styles part on open ("repaired" / corrupted file).
        head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 15})
        sub_heading = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10,
             'border': 1, 'bg_color': '#D3D3D3',
             'border_color': 'black'})
        filter_head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10,
             'border': 1, 'bg_color': '#D3D3D3',
             'border_color': 'black'})
        filter_body = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10})
        side_heading_sub = workbook.add_format(
            {'align': 'left', 'bold': True, 'font_size': 10,
             'border': 1,
             'border_color': 'black'})
        side_heading_sub.set_indent(1)
        txt_name = workbook.add_format({'font_size': 10, 'border': 1})
        txt_name.set_indent(2)
        account_heading = workbook.add_format(
            {'font_size': 10, 'border': 1, 'bold': True, 'bg_color': '#FFFF00'})
        account_heading.set_indent(1)
        # Cellules montant : vrai nombre (utilisable dans des formules
        # Excel) avec un format d'affichage numérique, au lieu d'une
        # chaîne pré-formatée ("1,234.56") qui apparaît figée/verrouillée.
        txt_name_amount = workbook.add_format(
            {'font_size': 10, 'border': 1, 'num_format': AMOUNT_NUM_FORMAT})
        txt_name_amount.set_indent(2)
        account_heading_amount = workbook.add_format(
            {'font_size': 10, 'border': 1, 'bold': True, 'bg_color': '#FFFF00',
             'num_format': AMOUNT_NUM_FORMAT})
        account_heading_amount.set_indent(1)
        filter_head_amount = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10,
             'border': 1, 'bg_color': '#D3D3D3', 'border_color': 'black',
             'num_format': AMOUNT_NUM_FORMAT})
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 20)
        sheet.set_column(2, 2, 15)
        sheet.set_column(3, 3, 15)
        col = 0
        sheet.write('A1:b1', report_name, head)
        sheet.write('B3:b4', 'Plage de dates', filter_head)
        sheet.write('B4:b4', 'Journaux', filter_head)
        sheet.write('B5:b4', 'Analytique', filter_head)
        sheet.write('B6:b4', 'Options', filter_head)
        if start_date or end_date:
            sheet.merge_range('C3:G3', f"{start_date} to {end_date}",
                              filter_body)
        else:
            sheet.merge_range('C3:G3', 'Toutes les dates', filter_body)
        if data['filters']['journal']:
            display_names = [journal for
                             journal in data['filters']['journal']]
            display_names_str = ', '.join(display_names)
            sheet.merge_range('C4:G4', display_names_str, filter_body)
        else:
            sheet.merge_range('C4:G4', 'Tous les journaux', filter_body)
        if data['filters']['analytic']:
            display_names = [analytic for
                             analytic in data['filters']['analytic']]
            account_keys_str = ', '.join(display_names)
            sheet.merge_range('C5:G5', account_keys_str, filter_body)
        else:
            sheet.merge_range('C5:G5', 'Tous', filter_body)
        if data['filters']['options']:
            option_keys = list(data['filters']['options'].keys())
            option_keys_str = ', '.join(option_keys)
            sheet.merge_range('C6:G6', option_keys_str, filter_body)
        else:
            sheet.merge_range('C6:G6', 'Écritures validées', filter_body)
        if data:
            sheet.write(8, col, ' ', sub_heading)
            sheet.write(8, col + 1, 'Date', sub_heading)
            sheet.merge_range('C9:E9', 'Communication', sub_heading)
            sheet.merge_range('F9:G9', 'Partenaire', sub_heading)
            sheet.merge_range('H9:I9', 'Débit', sub_heading)
            sheet.merge_range('J9:K9', 'Crédit', sub_heading)
            sheet.merge_range('L9:M9', 'Solde', sub_heading)
            row = 8
            # Defensive .get() with fallbacks throughout: a missing/None
            # key here used to raise (KeyError/TypeError), which the
            # controller's except-block turned into a JSON error response
            # saved as a .xlsx file by the browser - i.e. a "corrupted"
            # download instead of a clear failure. Now it degrades to an
            # incomplete-but-valid spreadsheet instead.
            account_list = data.get('account') or []
            account_total = data.get('total') or {}
            grand_total = data.get('grand_total') or {}
            # Move-line detail is fetched here, server-side, instead of
            # being pre-fetched in JS and shipped through the POST body:
            # for a general ledger with many accounts/entries that body
            # could exceed the web server's request size limit (413
            # Request Entity Too Large). Only small filter values and
            # account ids travel from the client now.
            account_ids = data.get('account_ids') or [
                acc.get('account_id') for acc in account_total.values()
                if acc.get('account_id')
            ]
            account_data = self.get_export_lines(
                account_ids,
                data.get('journal_ids'),
                data.get('date_range'),
                data.get('options'),
                data.get('analytic_ids'),
                data.get('method'),
            ) if account_ids else {}
            if account_list:
                for account in account_list:
                    row += 1
                    acc_totals = account_total.get(account) or {}
                    # Ligne récapitulative du compte : solde initial +
                    # mouvements de la période (pas seulement les
                    # mouvements), pour que le solde de fin de mois se
                    # retrouve bien comme solde de départ le mois suivant.
                    initial_debit = acc_totals.get('initial_debit', 0.0)
                    initial_credit = acc_totals.get('initial_credit', 0.0)
                    total_debit = acc_totals.get('total_debit', 0.0)
                    total_credit = acc_totals.get('total_credit', 0.0)
                    combined_debit = acc_totals.get('combined_debit', initial_debit + total_debit)
                    combined_credit = acc_totals.get('combined_credit', initial_credit + total_credit)
                    balance = acc_totals.get('balance', combined_debit - combined_credit)

                    sheet.write(row, col, account, account_heading)
                    sheet.write(row, col + 1, ' ', account_heading)
                    sheet.merge_range(row, col + 2, row, col + 4, ' ', account_heading)
                    sheet.merge_range(row, col + 5, row, col + 6, ' ',
                                      account_heading)
                    sheet.merge_range(row, col + 7, row, col + 8,
                                      to_float(combined_debit),
                                      account_heading_amount)
                    sheet.merge_range(row, col + 9, row, col + 10,
                                      to_float(combined_credit),
                                      account_heading_amount)
                    sheet.merge_range(row, col + 11, row, col + 12,
                                      to_float(balance),
                                      account_heading_amount)

                    initial_balance = acc_totals.get('initial_balance', 0.0)
                    if initial_balance:
                        row += 1
                        sheet.write(row, col, '', txt_name)
                        sheet.write(row, col + 1, ' ', txt_name)
                        sheet.merge_range(row, col + 2, row, col + 4, 'Solde initial', account_heading)
                        sheet.merge_range(row, col + 5, row, col + 6, ' ', txt_name)
                        sheet.merge_range(row, col + 7, row, col + 8,
                                          to_float(initial_debit), txt_name_amount)
                        sheet.merge_range(row, col + 9, row, col + 10,
                                          to_float(initial_credit), txt_name_amount)
                        sheet.merge_range(row, col + 11, row, col + 12,
                                          to_float(initial_balance), txt_name_amount)

                    for rec in account_data.get(acc_totals.get('account_id'), []):
                        row += 1
                        partner = rec.get('partner_id')
                        name = partner[1] if partner else None
                        # Handle both list of dicts (new) and list of lists (old) gracefully
                        move_data = rec[0] if isinstance(rec, list) else rec
                        sheet.write(row, col, move_data.get('move_name', ''), txt_name)
                        sheet.write(row, col + 1, str(move_data.get('date', '')), txt_name)
                        sheet.merge_range(row, col + 2, row, col + 4,
                                          move_data.get('name', ''), txt_name)
                        sheet.merge_range(row, col + 5, row, col + 6, name or ' ',
                                          txt_name)
                        sheet.merge_range(row, col + 7, row, col + 8,
                                          to_float(move_data.get('debit', 0.0)),
                                          txt_name_amount)
                        sheet.merge_range(row, col + 9, row, col + 10,
                                          to_float(move_data.get('credit', 0.0)),
                                          txt_name_amount)
                        sheet.merge_range(row, col + 11, row, col + 12,
                                          to_float(move_data.get('balance', 0.0)),
                                          txt_name_amount)
                row += 1
                sheet.merge_range(row, col, row, col + 6, 'Total',
                                  filter_head)
                sheet.merge_range(row, col + 7, row, col + 8,
                                  to_float(grand_total.get('total_debit', 0)),
                                  filter_head_amount)
                sheet.merge_range(row, col + 9, row, col + 10,
                                  to_float(grand_total.get('total_credit', 0)),
                                  filter_head_amount)
                sheet.merge_range(row, col + 11, row, col + 12,
                                  to_float(grand_total.get('total_debit', 0)) -
                                  to_float(grand_total.get('total_credit', 0)),
                                  filter_head_amount)
            else:
                sheet.write(row + 1, col, 'Aucune donnée pour les filtres sélectionnés', txt_name)
        workbook.close()
        output.seek(0)
        response.data = output.read()
        output.close()


class IrActionsReportGeneralLedger(models.Model):
    """Fetches General Ledger move-line detail server-side when the PDF is
    rendered, instead of the client fetching it via RPC and shipping it back
    through the report action's `data` payload. For a general ledger with
    many accounts/entries that payload could exceed the web server's request
    size limit (413 Request Entity Too Large). Only small filter values and
    account ids travel from the client now.
    """
    _inherit = 'ir.actions.report'

    def _get_report_values(self, docids, data=None):
        if self.report_name == 'dynamic_accounts_report.general_ledger':
            data = data or {}
            # Le template qweb fait des accès directs total[account][...],
            # filters['...'], grand_total['...'] (pas de .get()) : si le
            # client envoie une de ces clés vide/absente (None - ex. PDF
            # imprimé avant la fin du chargement des données), on plantait
            # avec "'NoneType' object is not subscriptable". On réécrit ici
            # des valeurs sûres dans `data` lui-même (pas seulement une
            # variable locale), puisque c'est `data` qui est passé tel quel
            # au contexte de rendu du template.
            account_total = data.get('total') or {}
            data['total'] = account_total
            data['account'] = data.get('account') or []
            data['grand_total'] = data.get('grand_total') or {}
            filters = data.get('filters') or {}
            filters.setdefault('start_date', None)
            filters.setdefault('end_date', None)
            filters.setdefault('journal', [])
            filters.setdefault('analytic', [])
            filters.setdefault('options', {})
            data['filters'] = filters
            account_ids = data.get('account_ids') or [
                acc.get('account_id') for acc in account_total.values()
                if acc.get('account_id')
            ]
            data['account_data'] = self.env['account.general.ledger'].get_export_lines(
                account_ids,
                data.get('journal_ids'),
                data.get('date_range'),
                data.get('options'),
                data.get('analytic_ids'),
                data.get('method'),
            ) if account_ids else {}
        return super()._get_report_values(docids, data=data)
