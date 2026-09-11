# -*- coding: utf-8 -*-
import io
import json
import xlsxwriter
from odoo import api, fields, models
from .report_xlsx_utils import to_float, AMOUNT_NUM_FORMAT


class AgePayableReport(models.TransientModel):
    """For creating Age Payable report"""
    _name = 'age.payable.report'
    _description = 'Aged Payable Report'

    def _compute_partner_totals(self, paid, currency_id):
        """Compute per-partner aged totals.

        `paid` is already the result of a single search() call, so this reads
        (date_maturity, credit, partner_id) once via a single read() batch call
        and buckets everything in one Python pass — O(n) instead of the
        previous O(partners x n) pattern (a fresh .filtered() re-scan of the
        whole recordset for every partner).
        """
        today = fields.Date.today()
        partner_total = {}
        if not paid:
            return partner_total

        lines_data = paid.read(['partner_id', 'date_maturity', 'credit'])
        buckets = {}
        for line in lines_data:
            partner = line['partner_id']
            if not partner or not line['date_maturity']:
                continue
            partner_id, partner_name = partner
            bucket = buckets.setdefault(partner_id, {
                'name': partner_name, 'd0': 0.0, 'd1': 0.0, 'd2': 0.0,
                'd3': 0.0, 'd4': 0.0, 'd5': 0.0, 'credit_sum': 0.0,
            })
            diff = (today - line['date_maturity']).days
            c = line['credit']
            bucket['credit_sum'] += c
            if diff <= 0:
                bucket['d0'] += c
            elif diff <= 30:
                bucket['d1'] += c
            elif diff <= 60:
                bucket['d2'] += c
            elif diff <= 90:
                bucket['d3'] += c
            elif diff <= 120:
                bucket['d4'] += c
            else:
                bucket['d5'] += c

        for partner_id, b in buckets.items():
            if b['credit_sum'] <= 0:
                continue
            partner_total[b['name']] = {
                'credit_sum': round(b['credit_sum'], 2),
                'diff0_sum': round(b['d0'], 2),
                'diff1_sum': round(b['d1'], 2),
                'diff2_sum': round(b['d2'], 2),
                'diff3_sum': round(b['d3'], 2),
                'diff4_sum': round(b['d4'], 2),
                'diff5_sum': round(b['d5'], 2),
                'currency_id': currency_id,
                'partner_id': partner_id,
                '_lines_loaded': False,
                '_lines': [],
                '_expanded': False,
                '_loading': False,
            }
        return partner_total

    @api.model
    def view_report(self):
        """Generate a report with aged payable data by partner (totals only)."""
        paid = self.env['account.move.line'].search([
            ('parent_state', '=', 'posted'),
            ('account_type', '=', 'liability_payable'),
            ('reconciled', '=', False)
        ])
        currency_id = self.env.company.currency_id.symbol
        partner_total = self._compute_partner_totals(paid, currency_id)
        partners = sorted(partner_total.keys(), key=lambda n: (n or '').lower())
        return {'partner_totals': partner_total, 'partners': partners}

    @api.model
    def get_filter_values(self, date, partner, account_search=None, partner_search=None,
                           piece_search=None):
        """Retrieve filtered aged payable data (totals only, fast)."""
        domain = [
            ('parent_state', '=', 'posted'),
            ('account_type', '=', 'liability_payable'),
            ('reconciled', '=', False)
        ]
        if date:
            domain.append(('date', '<=', date))
        if account_search:
            domain += ['|', ('account_id.code', 'ilike', account_search),
                        ('account_id.name', 'ilike', account_search)]
        if piece_search:
            domain += ['|', '|',
                        ('move_id.name', 'ilike', piece_search),
                        ('move_id.ref', 'ilike', piece_search),
                        ('name', 'ilike', piece_search)]
        paid = self.env['account.move.line'].search(domain)

        if partner:
            partner_ids = self.env['res.partner'].browse(partner)
            paid = paid.filtered(lambda l: l.partner_id.id in partner)

        currency_id = self.env.company.currency_id.symbol
        partner_total = self._compute_partner_totals(paid, currency_id)
        # "Contact" ne filtre pas les écritures mais restreint la liste des
        # partenaires affichés (comme le fait "Compte" pour le Grand Livre).
        if partner_search:
            partner_total = {
                name: v for name, v in partner_total.items()
                if partner_search.lower() in (name or '').lower()
            }
        # Triés par nom de partenaire, pas dans l'ordre d'apparition des
        # écritures.
        partners = sorted(partner_total.keys(), key=lambda n: (n or '').lower())
        return {'partner_totals': partner_total, 'partners': partners}

    @api.model
    def get_partner_aged_lines(self, partner_id, date, account_search=None, piece_search=None):
        """Lazy-load aged payable detail lines for a single partner."""
        domain = [
            ('parent_state', '=', 'posted'),
            ('account_type', '=', 'liability_payable'),
            ('reconciled', '=', False),
            ('partner_id', '=', partner_id)
        ]
        if date:
            domain.append(('date', '<=', date))
        if account_search:
            domain += ['|', ('account_id.code', 'ilike', account_search),
                        ('account_id.name', 'ilike', account_search)]
        if piece_search:
            domain += ['|', '|',
                        ('move_id.name', 'ilike', piece_search),
                        ('move_id.ref', 'ilike', piece_search),
                        ('name', 'ilike', piece_search)]

        lines = self.env['account.move.line'].search(domain, order='date_maturity asc', limit=500)
        today = fields.Date.today()
        result = []
        for line in lines:
            diff = (today - line.date_maturity).days if line.date_maturity else 0
            data = line.read(['name', 'move_name', 'date', 'amount_currency',
                              'account_id', 'date_maturity', 'currency_id', 'credit', 'move_id'])[0]
            data['diff0'] = data['credit'] if diff <= 0 else 0.0
            data['diff1'] = data['credit'] if 0 < diff <= 30 else 0.0
            data['diff2'] = data['credit'] if 30 < diff <= 60 else 0.0
            data['diff3'] = data['credit'] if 60 < diff <= 90 else 0.0
            data['diff4'] = data['credit'] if 90 < diff <= 120 else 0.0
            data['diff5'] = data['credit'] if diff > 120 else 0.0
            result.append(data)
        return result

    @api.model
    def get_export_lines(self, partner_ids, date, account_search=None, piece_search=None):
        """
        Fetch aged detail lines for MULTIPLE partners in a single query,
        grouped by partner id.

        On-screen, lines are only lazy-loaded for a single partner when its
        row is expanded (get_partner_aged_lines), so the PDF export - which
        needs the per-partner detail, unlike the Excel export which is
        summary-only - never had access to any of it. This fetches
        everything needed in one go, keyed by partner id (not name, since
        two different partners can share the same display name).
        """
        if not partner_ids:
            return {}
        domain = [
            ('parent_state', '=', 'posted'),
            ('account_type', '=', 'liability_payable'),
            ('reconciled', '=', False),
            ('partner_id', 'in', partner_ids),
        ]
        if date:
            domain.append(('date', '<=', date))
        if account_search:
            domain += ['|', ('account_id.code', 'ilike', account_search),
                        ('account_id.name', 'ilike', account_search)]
        if piece_search:
            domain += ['|', '|',
                        ('move_id.name', 'ilike', piece_search),
                        ('move_id.ref', 'ilike', piece_search),
                        ('name', 'ilike', piece_search)]

        lines = self.env['account.move.line'].search(domain, order='partner_id, date_maturity asc')
        today = fields.Date.today()
        result = {}
        for line in lines:
            partner = line.partner_id
            if not partner:
                continue
            diff = (today - line.date_maturity).days if line.date_maturity else 0
            data = line.read(['name', 'move_name', 'date', 'amount_currency',
                              'account_id', 'date_maturity', 'currency_id', 'credit', 'move_id'])[0]
            data['diff0'] = data['credit'] if diff <= 0 else 0.0
            data['diff1'] = data['credit'] if 0 < diff <= 30 else 0.0
            data['diff2'] = data['credit'] if 30 < diff <= 60 else 0.0
            data['diff3'] = data['credit'] if 60 < diff <= 90 else 0.0
            data['diff4'] = data['credit'] if 90 < diff <= 120 else 0.0
            data['diff5'] = data['credit'] if diff > 120 else 0.0
            result.setdefault(partner.id, []).append(data)
        return result

    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """Generate an Excel report based on the provided data."""
        data = json.loads(data)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        end_date = data['filters'].get('end_date', '')
        sheet = workbook.add_worksheet()
        head = workbook.add_format({'align': 'center', 'bold': True, 'font_size': 15})
        sub_heading = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10,
             'border': 1, 'bg_color': '#D3D3D3', 'border_color': 'black'})
        filter_head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10,
             'border': 1, 'bg_color': '#D3D3D3', 'border_color': 'black'})
        filter_body = workbook.add_format({'align': 'center', 'bold': True, 'font_size': 10})
        txt_name = workbook.add_format({'font_size': 10, 'border': 1})
        txt_name.set_indent(2)
        # Cellules montant : vrai nombre (utilisable dans des formules Excel)
        # avec un format d'affichage identique au "{:,.2f}" utilisé avant.
        amount_format = workbook.add_format({'font_size': 10, 'border': 1, 'num_format': AMOUNT_NUM_FORMAT})
        amount_format.set_indent(2)
        filter_head_amount = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10,
             'border': 1, 'bg_color': '#D3D3D3', 'border_color': 'black', 'num_format': AMOUNT_NUM_FORMAT})
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 20)
        col = 0
        sheet.write('A1:b1', report_name, head)
        sheet.write('B3:b4', 'Date Range', filter_head)
        sheet.write('B4:b4', 'Partners', filter_head)
        if end_date:
            sheet.merge_range('C3:G3', end_date, filter_body)
        if data['filters'].get('partner'):
            partners_str = ', '.join([p.get('display_name', '') for p in data['filters']['partner']])
            sheet.merge_range('C4:G4', partners_str, filter_body)

        if data:
            # No report_action string-match guard here: this method is only
            # ever used for this report's own export, and gating content on
            # an exact match of the client action's xml_id (which isn't
            # always populated the same way) previously made the General
            # Ledger export silently skip all its content - "no data".
            sheet.write(7, col, 'Partner', sub_heading)
            sheet.merge_range(7, col + 1, 7, col + 2, 'Not Due', sub_heading)
            sheet.merge_range(7, col + 3, 7, col + 4, '1-30 Days', sub_heading)
            sheet.merge_range(7, col + 5, 7, col + 6, '31-60 Days', sub_heading)
            sheet.merge_range(7, col + 7, 7, col + 8, '61-90 Days', sub_heading)
            sheet.merge_range(7, col + 9, 7, col + 10, '91-120 Days', sub_heading)
            sheet.merge_range(7, col + 11, 7, col + 12, '> 120 Days', sub_heading)
            sheet.merge_range(7, col + 13, 7, col + 14, 'Total', sub_heading)

            row = 7
            partners = data.get('partners', []) or []
            total_vals = [0.0] * 7
            for partner in partners:
                p = data.get('total', {}).get(partner, {})
                row += 1
                values = [p.get('diff0_sum', 0), p.get('diff1_sum', 0), p.get('diff2_sum', 0),
                          p.get('diff3_sum', 0), p.get('diff4_sum', 0), p.get('diff5_sum', 0),
                          p.get('credit_sum', 0)]
                for i, v in enumerate(values):
                    total_vals[i] += v
                sheet.write(row, col, partner, txt_name)
                sheet.merge_range(row, col + 1, row, col + 2, to_float(values[0]), amount_format)
                sheet.merge_range(row, col + 3, row, col + 4, to_float(values[1]), amount_format)
                sheet.merge_range(row, col + 5, row, col + 6, to_float(values[2]), amount_format)
                sheet.merge_range(row, col + 7, row, col + 8, to_float(values[3]), amount_format)
                sheet.merge_range(row, col + 9, row, col + 10, to_float(values[4]), amount_format)
                sheet.merge_range(row, col + 11, row, col + 12, to_float(values[5]), amount_format)
                sheet.merge_range(row, col + 13, row, col + 14, to_float(values[6]), amount_format)

            row += 1
            sheet.write(row, col, 'Total', filter_head)
            sheet.merge_range(row, col + 1, row, col + 2, to_float(total_vals[0]), filter_head_amount)
            sheet.merge_range(row, col + 3, row, col + 4, to_float(total_vals[1]), filter_head_amount)
            sheet.merge_range(row, col + 5, row, col + 6, to_float(total_vals[2]), filter_head_amount)
            sheet.merge_range(row, col + 7, row, col + 8, to_float(total_vals[3]), filter_head_amount)
            sheet.merge_range(row, col + 9, row, col + 10, to_float(total_vals[4]), filter_head_amount)
            sheet.merge_range(row, col + 11, row, col + 12, to_float(total_vals[5]), filter_head_amount)
            sheet.merge_range(row, col + 13, row, col + 14, to_float(total_vals[6]), filter_head_amount)

        workbook.close()
        output.seek(0)
        response.data = output.read()
        output.close()


class ReportAgedPayable(models.AbstractModel):
    """Contexte de rendu du PDF Aged Payable.

    Odoo n'appelle `_get_report_values` que sur un modèle nommé
    'report.<module>.<report_name>' (voir
    odoo/addons/base/models/ir_actions_report.py,
    _get_rendering_context) - jamais sur 'ir.actions.report' lui-même.
    La version précédente de ce correctif déclarait la surcharge sur
    'ir.actions.report' (`_inherit`), que le moteur de rendu n'invoque
    pas : les lignes de détail n'arrivaient donc jamais au template et
    `data` restait absent du contexte.

    Les lignes ne sont chargées à l'écran que pour le partenaire déplié
    (get_partner_aged_lines) : le serveur les récupère lui-même ici, à
    partir des seuls totaux (qui portent déjà chaque partner_id) et des
    filtres, sans les faire transiter par le payload du client.
    """
    _name = 'report.dynamic_accounts_report.aged_payable'
    _description = 'Aged Payable Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        totals = data.get('total') or {}
        filters = data.get('filters') or {}
        filters.setdefault('end_date', None)
        filters.setdefault('partner', [])
        partner_ids = [
            p.get('partner_id') for p in totals.values()
            if p.get('partner_id')
        ]
        lines_by_partner = self.env['age.payable.report'].get_export_lines(
            partner_ids, data.get('date'),
            data.get('account_search'), data.get('piece_search'),
        ) if partner_ids else {}
        # Re-key by partner name to match what the template
        # (move_lines/total) already indexes by.
        lines_by_name = {
            name: lines_by_partner.get(p.get('partner_id'), [])
            for name, p in totals.items()
        }
        return {
            'doc_ids': docids,
            'doc_model': 'age.payable.report',
            'docs': self.env['age.payable.report'].browse(docids or []),
            'report_name': data.get('report_name') or data.get('title') or '',
            'move_lines': data.get('move_lines') or [],
            'total': totals,
            'grand_total': data.get('grand_total') or {},
            'filters': filters,
            'data': lines_by_name,
        }
