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
import calendar
import io
import json
from datetime import datetime
import xlsxwriter
from odoo import models, fields, api
from odoo.tools.date_utils import get_month, get_fiscal_year, \
    get_quarter_number, subtract
from .report_xlsx_utils import to_float, AMOUNT_NUM_FORMAT


class TaxReport(models.TransientModel):
    """For creating Tax report."""
    _name = 'tax.report'
    _description = 'Tax Report'

    @api.model
    def view_report(self):
        """
        View a tax report for the current month. This function retrieves
        tax-related information for the current month. It calculates the net
        amount and tax amount for both sales and purchases based on the tax
        information associated with account move lines.

        Previously this scanned EVERY account.move.line in the database just
        to enumerate which taxes exist (`search([]).mapped('tax_ids')`), then
        issued one extra search() per tax. Taxes are looked up directly from
        account.tax instead, and their totals computed with a single
        read_group (grouping by a many2many field works fine in Odoo and
        returns one row per tax) instead of one query per tax.

            :return: Dictionary containing sale and purchase data for the
                     current month.
        """
        sale = []
        purchase = []
        today = fields.Date.today()
        month_start, month_end = get_month(today)

        taxes = self.env['account.tax'].search([('type_tax_use', 'in', ['sale', 'purchase'])])
        groups = self.env['account.move.line'].read_group(
            domain=[('tax_ids', 'in', taxes.ids), ('parent_state', '=', 'posted'),
                    ('date', '>=', month_start), ('date', '<=', month_end)],
            fields=['tax_ids', 'debit:sum', 'credit:sum'],
            groupby=['tax_ids'],
        )
        totals_map = {g['tax_ids'][0]: g for g in groups if g.get('tax_ids')}

        for tax in taxes:
            g = totals_map.get(tax.id, {})
            tax_debit_sums = g.get('debit') or 0.0
            tax_credit_sums = g.get('credit') or 0.0
            entry = {
                'name': tax.name,
                'amount': tax.amount,
                'net': round(tax_debit_sums + tax_credit_sums, 2),
                'tax': round((tax_debit_sums + tax_credit_sums) * (
                        tax.amount / 100), 2)
            }
            if tax.type_tax_use == 'sale':
                sale.append(entry)
            elif tax.type_tax_use == 'purchase':
                purchase.append(entry)
        return {
            'sale': sale,
            'purchase': purchase
        }

    @api.model
    def get_filter_values(self, start_date, end_date, comparison_number,
                          comparison_type, options, report_type):
        """
           Get filtered tax values based on various criteria.

           :param start_date: Start date of the filter period.
           :param end_date: End date of the filter period.
           :param comparison_number: Number of comparison periods.
           :param comparison_type: Type of comparison (year, month, quarter).
           :param options: Filter options.
           :param report_type: Type of report (account, tax).
           :return: Dictionary containing dynamic_date_num, sale, and purchase
                    data.
           """
        sale = []
        purchase = []
        dynamic_date_num = {}
        if options == {}:
            options = None
        if options is None:
            option_domain = ['posted']
        elif 'draft' in options:
            option_domain = ['posted', 'draft']
        # Taxes triées par séquence (comme account.tax), pas dans l'ordre
        # d'apparition dans les écritures.
        tax_ids = self.env['account.move.line'].search([]).mapped(
            'tax_ids').sorted(key=lambda t: (t.sequence, t.id))
        start_date_first = \
            get_fiscal_year(datetime.strptime(start_date, "%Y-%m-%d").date())[
                0] if comparison_type == 'year' else datetime.strptime(
                start_date, "%Y-%m-%d").date()
        end_date_first = \
            get_fiscal_year(datetime.strptime(end_date, "%Y-%m-%d").date())[
                1] if comparison_type == 'year' else datetime.strptime(
                end_date, "%Y-%m-%d").date()
        if report_type is not None and 'account' in report_type:
            start_date = start_date_first
            end_date = end_date_first
            # Comptes triés par code (plan comptable), pas dans l'ordre
            # d'apparition dans les écritures.
            account_ids = self.env['account.move.line'].search([]).mapped(
                'account_id').sorted(key=lambda a: a.code or '')
            for account in account_ids:
                tax_ids = self.env['account.move.line'].search(
                    [('account_id', '=', account.id)]).mapped('tax_ids')
                if tax_ids:
                    for tax in tax_ids:
                        dynamic_total_tax_sum = {}
                        dynamic_total_net_sum = {}
                        if comparison_number:
                            if comparison_type == 'year':
                                start_date = start_date_first
                                end_date = end_date_first
                                for i in range(1, int(comparison_number) + 1):
                                    com_start_date = subtract(start_date,
                                                              years=i)
                                    com_end_date = subtract(end_date, years=i)
                                    tax_id = self.env[
                                        'account.move.line'].search(
                                        [('tax_ids', '=', tax.id),
                                         ('date', '>=', com_start_date),
                                         ('date', '<=', com_end_date),
                                         ('account_id', '=', account.id),
                                         ('parent_state', 'in',
                                          option_domain)]).read(
                                        ['debit', 'credit'])
                                    tax_debit_sums = sum(
                                        record['debit'] for record in tax_id)
                                    tax_credit_sums = sum(
                                        record['credit'] for record in tax_id)
                                    dynamic_total_net_sum[
                                        f"dynamic_total_net_sum{i}"] = tax_debit_sums + tax_credit_sums
                                    dynamic_total_tax_sum[
                                        f"dynamic_total_tax_sum{i}"] = \
                                        dynamic_total_net_sum[
                                            f"dynamic_total_net_sum{i}"] * (
                                                tax.amount / 100)
                            elif comparison_type == 'month':
                                dynamic_date_num[
                                    f"dynamic_date_num{0}"] = self.get_month_name(
                                    start_date) + ' ' + str(start_date.year)
                                for i in range(1, int(comparison_number) + 1):
                                    com_start_date = subtract(start_date,
                                                              months=i)
                                    com_end_date = subtract(end_date, months=i)
                                    tax_id = self.env[
                                        'account.move.line'].search(
                                        [('tax_ids', '=', tax.id),
                                         ('date', '>=', com_start_date),
                                         ('account_id', '=', account.id),
                                         ('date', '<=', com_end_date),
                                         ('parent_state', 'in',
                                          option_domain)]).read(
                                        ['debit', 'credit'])
                                    tax_debit_sums = sum(
                                        record['debit'] for record in tax_id)
                                    tax_credit_sums = sum(
                                        record['credit'] for record in tax_id)
                                    dynamic_total_net_sum[
                                        f"dynamic_total_net_sum{i}"] = tax_debit_sums + tax_credit_sums
                                    dynamic_total_tax_sum[
                                        f"dynamic_total_tax_sum{i}"] = \
                                        dynamic_total_net_sum[
                                            f"dynamic_total_net_sum{i}"] * (
                                                tax.amount / 100)
                                    dynamic_date_num[
                                        f"dynamic_date_num{i}"] = self.get_month_name(
                                        com_start_date) + ' ' + str(
                                        com_start_date.year)
                            elif comparison_type == 'quarter':
                                dynamic_date_num[
                                    f"dynamic_date_num{0}"] = 'Q' + ' ' + str(
                                    get_quarter_number(
                                        start_date)) + ' ' + str(
                                    start_date.year)
                                for i in range(1, int(comparison_number) + 1):
                                    com_start_date = subtract(start_date,
                                                              months=i * 3)
                                    com_end_date = subtract(end_date,
                                                            months=i * 3)
                                    tax_id = self.env[
                                        'account.move.line'].search(
                                        [('tax_ids', '=', tax.id),
                                         ('date', '>=', com_start_date),
                                         ('account_id', '=', account.id),
                                         ('date', '<=', com_end_date),
                                         ('parent_state', 'in',
                                          option_domain)]).read(
                                        ['debit', 'credit'])
                                    tax_debit_sums = sum(
                                        record['debit'] for record in tax_id)
                                    tax_credit_sums = sum(
                                        record['credit'] for record in tax_id)
                                    dynamic_total_net_sum[
                                        f"dynamic_total_net_sum{i}"] = tax_debit_sums + tax_credit_sums
                                    dynamic_total_tax_sum[
                                        f"dynamic_total_tax_sum{i}"] = \
                                        dynamic_total_net_sum[
                                            f"dynamic_total_net_sum{i}"] * (
                                                tax.amount / 100)
                                    dynamic_date_num[
                                        f"dynamic_date_num{i}"] = 'Q' + ' ' + str(
                                        get_quarter_number(
                                            com_start_date)) + ' ' + str(
                                        com_start_date.year)
                        tax_id = self.env['account.move.line'].search(
                            [('tax_ids', '=', tax.id),
                             ('date', '>=', start_date_first),
                             ('date', '<=', end_date_first),
                             ('parent_state', 'in', option_domain),
                             ('account_id', '=', account.id)]).read(
                            ['debit', 'credit'])
                        tax_debit_sums = sum(
                            record['debit'] for record in tax_id)
                        tax_credit_sums = sum(
                            record['credit'] for record in tax_id)
                        if tax_id and tax.type_tax_use == 'sale':
                            if comparison_number:
                                sale.append({
                                    'name': tax.name,
                                    'amount': tax.amount,
                                    'net': round(
                                        tax_debit_sums + tax_credit_sums,
                                        2),
                                    'tax': round(
                                        (tax_debit_sums + tax_credit_sums) * (
                                                tax.amount / 100), 2),
                                    'dynamic net': dynamic_total_net_sum,
                                    'dynamic tax': dynamic_total_tax_sum,
                                    'account': account.display_name,
                                })
                            else:
                                sale.append({
                                    'name': tax.name,
                                    'amount': tax.amount,
                                    'net': round(
                                        tax_debit_sums + tax_credit_sums,
                                        2),
                                    'tax': round(
                                        (tax_debit_sums + tax_credit_sums) * (
                                                tax.amount / 100), 2),
                                    'account': account.display_name,
                                })
                        elif tax_id and tax.type_tax_use == 'purchase':
                            if comparison_number:
                                purchase.append({
                                    'name': tax.name,
                                    'amount': tax.amount,
                                    'net': round(
                                        tax_debit_sums + tax_credit_sums,
                                        2),
                                    'tax': round(
                                        (tax_debit_sums + tax_credit_sums) * (
                                                tax.amount / 100), 2),
                                    'dynamic net': dynamic_total_net_sum,
                                    'dynamic tax': dynamic_total_tax_sum,
                                    'account': account.display_name,
                                })
                            else:
                                purchase.append({
                                    'name': tax.name,
                                    'amount': tax.amount,
                                    'net': round(
                                        tax_debit_sums + tax_credit_sums,
                                        2),
                                    'tax': round(
                                        (tax_debit_sums + tax_credit_sums) * (
                                                tax.amount / 100), 2),
                                    'account': account.display_name,
                                })
        elif report_type is not None and 'tax' in report_type:
            start_date = start_date_first
            end_date = end_date_first
            for tax in tax_ids:
                # Comptes triés par code (plan comptable), pas dans l'ordre
                # d'apparition dans les écritures.
                account_ids = self.env['account.move.line'].search(
                    [('tax_ids', '=', tax.id)]).mapped(
                    'account_id').sorted(key=lambda a: a.code or '')
                for account in account_ids:
                    dynamic_total_tax_sum = {}
                    dynamic_total_net_sum = {}
                    if comparison_number:
                        if comparison_type == 'year':
                            start_date = start_date_first
                            end_date = end_date_first
                            for i in range(1, int(comparison_number) + 1):
                                com_start_date = subtract(start_date,
                                                          years=i)
                                com_end_date = subtract(end_date, years=i)
                                tax_id = self.env[
                                    'account.move.line'].search(
                                    [('tax_ids', '=', tax.id),
                                     ('date', '>=', com_start_date),
                                     ('date', '<=', com_end_date),
                                     ('account_id', '=', account.id),
                                     ('parent_state', 'in',
                                      option_domain)]).read(
                                    ['debit', 'credit'])
                                tax_debit_sums = sum(
                                    record['debit'] for record in tax_id)
                                tax_credit_sums = sum(
                                    record['credit'] for record in tax_id)
                                dynamic_total_net_sum[
                                    f"dynamic_total_net_sum{i}"] = tax_debit_sums + tax_credit_sums
                                dynamic_total_tax_sum[
                                    f"dynamic_total_tax_sum{i}"] = \
                                    dynamic_total_net_sum[
                                        f"dynamic_total_net_sum{i}"] * (
                                            tax.amount / 100)
                        elif comparison_type == 'month':
                            dynamic_date_num[
                                f"dynamic_date_num{0}"] = self.get_month_name(
                                start_date) + ' ' + str(start_date.year)
                            for i in range(1, int(comparison_number) + 1):
                                com_start_date = subtract(start_date, months=i)
                                com_end_date = subtract(end_date, months=i)
                                tax_id = self.env[
                                    'account.move.line'].search(
                                    [('tax_ids', '=', tax.id),
                                     ('date', '>=', com_start_date),
                                     ('date', '<=', com_end_date),
                                     ('account_id', '=', account.id),
                                     ('parent_state', 'in',
                                      option_domain)]).read(
                                    ['debit', 'credit'])
                                tax_debit_sums = sum(
                                    record['debit'] for record in tax_id)
                                tax_credit_sums = sum(
                                    record['credit'] for record in tax_id)
                                dynamic_total_net_sum[
                                    f"dynamic_total_net_sum{i}"] = tax_debit_sums + tax_credit_sums
                                dynamic_total_tax_sum[
                                    f"dynamic_total_tax_sum{i}"] = \
                                    dynamic_total_net_sum[
                                        f"dynamic_total_net_sum{i}"] * (
                                            tax.amount / 100)
                                dynamic_date_num[
                                    f"dynamic_date_num{i}"] = self.get_month_name(
                                    com_start_date) + ' ' + str(
                                    com_start_date.year)
                        elif comparison_type == 'quarter':
                            dynamic_date_num[
                                f"dynamic_date_num{0}"] = 'Q' + ' ' + str(
                                get_quarter_number(start_date)) + ' ' + str(
                                start_date.year)
                            for i in range(1, int(comparison_number) + 1):
                                com_start_date = subtract(start_date,
                                                          months=i * 3)
                                com_end_date = subtract(end_date,
                                                        months=i * 3)
                                tax_id = self.env[
                                    'account.move.line'].search(
                                    [('tax_ids', '=', tax.id),
                                     ('date', '>=', com_start_date),
                                     ('date', '<=', com_end_date),
                                     ('account_id', '=', account.id),
                                     ('parent_state', 'in',
                                      option_domain)]).read(
                                    ['debit', 'credit'])
                                tax_debit_sums = sum(
                                    record['debit'] for record in tax_id)
                                tax_credit_sums = sum(
                                    record['credit'] for record in tax_id)
                                dynamic_total_net_sum[
                                    f"dynamic_total_net_sum{i}"] = tax_debit_sums + tax_credit_sums
                                dynamic_total_tax_sum[
                                    f"dynamic_total_tax_sum{i}"] = \
                                    dynamic_total_net_sum[
                                        f"dynamic_total_net_sum{i}"] * (
                                            tax.amount / 100)
                                dynamic_date_num[
                                    f"dynamic_date_num{i}"] = 'Q' + ' ' + str(
                                    get_quarter_number(
                                        com_start_date)) + ' ' + str(
                                    com_start_date.year)
                    tax_id = self.env['account.move.line'].search(
                        [('tax_ids', '=', tax.id),
                         ('parent_state', 'in', option_domain),
                         ('date', '>=', start_date_first),
                         ('date', '<=', end_date_first),
                         ('account_id', '=', account.id)]).read(
                        ['debit', 'credit'])
                    tax_debit_sums = sum(
                        record['debit'] for record in tax_id)
                    tax_credit_sums = sum(
                        record['credit'] for record in tax_id)
                    if tax_id and tax.type_tax_use == 'sale':
                        if comparison_number:
                            sale.append({
                                'name': tax.name,
                                'amount': tax.amount,
                                'net': round(tax_debit_sums + tax_credit_sums,
                                             2),
                                'tax': round(
                                    (tax_debit_sums + tax_credit_sums) * (
                                            tax.amount / 100), 2),
                                'dynamic net': dynamic_total_net_sum,
                                'dynamic tax': dynamic_total_tax_sum,
                                'account': account.display_name,
                            })
                        else:
                            sale.append({
                                'name': tax.name,
                                'amount': tax.amount,
                                'net': round(tax_debit_sums + tax_credit_sums,
                                             2),
                                'tax': round(
                                    (tax_debit_sums + tax_credit_sums) * (
                                            tax.amount / 100), 2),
                                'account': account.display_name,
                            })
                    elif tax_id and tax.type_tax_use == 'purchase':
                        if comparison_number:
                            purchase.append({
                                'name': tax.name,
                                'amount': tax.amount,
                                'net': round(tax_debit_sums + tax_credit_sums,
                                             2),
                                'tax': round(
                                    (tax_debit_sums + tax_credit_sums) * (
                                            tax.amount / 100), 2),
                                'dynamic net': dynamic_total_net_sum,
                                'dynamic tax': dynamic_total_tax_sum,
                                'account': account.display_name,
                            })
                        else:
                            purchase.append({
                                'name': tax.name,
                                'amount': tax.amount,
                                'net': round(tax_debit_sums + tax_credit_sums,
                                             2),
                                'tax': round(
                                    (tax_debit_sums + tax_credit_sums) * (
                                            tax.amount / 100), 2),
                                'account': account.display_name,
                            })
        else:
            start_date = start_date_first
            end_date = end_date_first
            for tax in tax_ids:
                dynamic_total_tax_sum = {}
                dynamic_total_net_sum = {}
                if comparison_number:
                    if comparison_type == 'year':
                        start_date = start_date_first
                        end_date = end_date_first
                        for i in range(1, int(comparison_number) + 1):
                            com_start_date = subtract(start_date,
                                                      years=i)
                            com_end_date = subtract(end_date, years=i)
                            tax_id = self.env[
                                'account.move.line'].search(
                                [('tax_ids', '=', tax.id),
                                 ('date', '>=', com_start_date),
                                 ('date', '<=', com_end_date),
                                 ('parent_state', 'in', option_domain)]).read(
                                ['debit', 'credit'])
                            tax_debit_sums = sum(
                                record['debit'] for record in tax_id)
                            tax_credit_sums = sum(
                                record['credit'] for record in tax_id)
                            dynamic_total_net_sum[
                                f"dynamic_total_net_sum{i}"] = tax_debit_sums + tax_credit_sums
                            dynamic_total_tax_sum[
                                f"dynamic_total_tax_sum{i}"] = \
                                dynamic_total_net_sum[
                                    f"dynamic_total_net_sum{i}"] * (
                                        tax.amount / 100)
                    elif comparison_type == 'month':
                        dynamic_date_num[
                            f"dynamic_date_num{0}"] = self.get_month_name(
                            start_date) + ' ' + str(start_date.year)
                        for i in range(1, int(comparison_number) + 1):
                            com_start_date = subtract(start_date, months=i)
                            com_end_date = subtract(end_date, months=i)
                            tax_id = self.env[
                                'account.move.line'].search(
                                [('tax_ids', '=', tax.id),
                                 ('date', '>=', com_start_date),
                                 ('date', '<=', com_end_date),
                                 ('parent_state', 'in', option_domain)]).read(
                                ['debit', 'credit'])
                            tax_debit_sums = sum(
                                record['debit'] for record in tax_id)
                            tax_credit_sums = sum(
                                record['credit'] for record in tax_id)
                            dynamic_total_net_sum[
                                f"dynamic_total_net_sum{i}"] = tax_debit_sums + tax_credit_sums
                            dynamic_total_tax_sum[
                                f"dynamic_total_tax_sum{i}"] = \
                                dynamic_total_net_sum[
                                    f"dynamic_total_net_sum{i}"] * (
                                        tax.amount / 100)
                            dynamic_date_num[
                                f"dynamic_date_num{i}"] = self.get_month_name(
                                com_start_date) + ' ' + str(
                                com_start_date.year)
                    elif comparison_type == 'quarter':
                        dynamic_date_num[
                            f"dynamic_date_num{0}"] = 'Q' + ' ' + str(
                            get_quarter_number(start_date)) + ' ' + str(
                            start_date.year)
                        for i in range(1, int(comparison_number) + 1):
                            com_start_date = subtract(start_date,
                                                      months=i * 3)
                            com_end_date = subtract(end_date,
                                                    months=i * 3)
                            tax_id = self.env[
                                'account.move.line'].search(
                                [('tax_ids', '=', tax.id),
                                 ('date', '>=', com_start_date),
                                 ('date', '<=', com_end_date),
                                 ('parent_state', 'in', option_domain)]).read(
                                ['debit', 'credit'])
                            tax_debit_sums = sum(
                                record['debit'] for record in tax_id)
                            tax_credit_sums = sum(
                                record['credit'] for record in tax_id)
                            dynamic_total_net_sum[
                                f"dynamic_total_net_sum{i}"] = tax_debit_sums + tax_credit_sums
                            dynamic_total_tax_sum[
                                f"dynamic_total_tax_sum{i}"] = \
                                dynamic_total_net_sum[
                                    f"dynamic_total_net_sum{i}"] * (
                                        tax.amount / 100)
                            dynamic_date_num[
                                f"dynamic_date_num{i}"] = 'Q' + ' ' + str(
                                get_quarter_number(
                                    com_start_date)) + ' ' + str(
                                com_start_date.year)
                tax_id = self.env['account.move.line'].search(
                    [('tax_ids', '=', tax.id),
                     ('parent_state', 'in', option_domain),
                     ('date', '>=', start_date_first),
                     ('date', '<=', end_date_first)]).read(['debit', 'credit'])
                tax_debit_sums = sum(record['debit'] for record in tax_id)
                tax_credit_sums = sum(record['credit'] for record in tax_id)
                if tax.type_tax_use == 'sale':
                    if comparison_number:
                        sale.append({
                            'name': tax.name,
                            'amount': tax.amount,
                            'net': round(tax_debit_sums + tax_credit_sums, 2),
                            'tax': round((tax_debit_sums + tax_credit_sums) * (
                                    tax.amount / 100), 2),
                            'dynamic net': dynamic_total_net_sum,
                            'dynamic tax': dynamic_total_tax_sum,
                        })
                    else:
                        sale.append({
                            'name': tax.name,
                            'amount': tax.amount,
                            'net': round(tax_debit_sums + tax_credit_sums, 2),
                            'tax': round((tax_debit_sums + tax_credit_sums) * (
                                    tax.amount / 100), 2),
                        })
                elif tax.type_tax_use == 'purchase':
                    if comparison_number:
                        purchase.append({
                            'name': tax.name,
                            'amount': tax.amount,
                            'net': round(tax_debit_sums + tax_credit_sums, 2),
                            'tax': round((tax_debit_sums + tax_credit_sums) * (
                                    tax.amount / 100), 2),
                            'dynamic net': dynamic_total_net_sum,
                            'dynamic tax': dynamic_total_tax_sum,
                        })
                    else:
                        purchase.append({
                            'name': tax.name,
                            'amount': tax.amount,
                            'net': round(tax_debit_sums + tax_credit_sums, 2),
                            'tax': round((tax_debit_sums + tax_credit_sums) * (
                                    tax.amount / 100), 2),
                        })
        return {
            'dynamic_date_num': dynamic_date_num,
            'sale': sale,
            'purchase': purchase
        }

    @api.model
    def get_month_name(self, date):
        """
        Retrieve the abbreviated name of the month for a given date.

        :param date: The date for which to retrieve the month's abbreviated
                     name.
        :type date: datetime.date
        :return: Abbreviated name of the month (e.g., 'Jan', 'Feb', ..., 'Dec').
        :rtype: str
        """
        month_names = calendar.month_abbr
        return month_names[date.month]

    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """
        Generate an XLSX report based on provided data and response stream.

        Generates an Excel workbook with specified report format, including
        subheadings,column headers, and row data for the given financial report
        data.

        :param str data: JSON-encoded data for the report.
        :param response: Response object to stream the generated report.
        :param str report_name: Name of the financial report.
        """
        data = json.loads(data)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet()
        sub_heading = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10,
             'border': 1,
             'border_color': 'black'})
        side_heading_sub = workbook.add_format(
            {'align': 'left', 'bold': True, 'font_size': 10,
             'border': 1,
             'border_color': 'black'})
        side_heading_sub.set_indent(1)
        txt_name = workbook.add_format({'font_size': 10, 'border': 1})
        txt_name.set_indent(2)
        # Cellules montant : vrai nombre (utilisable dans des formules Excel)
        # avec un format d'affichage identique au "{:,.2f}" utilisé pour
        # l'affichage à l'écran.
        amount_format = workbook.add_format(
            {'font_size': 10, 'border': 1, 'num_format': AMOUNT_NUM_FORMAT})
        amount_format.set_indent(2)
        total_amount_format = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': 10, 'border': 1,
             'border_color': 'black', 'num_format': AMOUNT_NUM_FORMAT})
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 20)
        sheet.set_column(2, 2, 15)
        sheet.set_column(3, 3, 15)
        col = 0
        sheet.write('A3:b4', report_name, sub_heading)
        sheet.write(5, col, '', sub_heading)
        i = 1
        for date_view in data['date_viewed']:
            sheet.merge_range(5, col + i, 5, col + i + 1, date_view,
                              sub_heading)
            i += 2
        j = 1
        prev_account = None
        prev_tax = None
        sheet.write(6, col, '', sub_heading)
        for date in data['date_viewed']:
            sheet.write(6, col + j, 'NET', sub_heading)
            sheet.write(6, col + j + 1, 'TAX', sub_heading)
            j += 1
        sheet.write(7, col, 'Sales', sub_heading)
        sheet.write(7, col + 1, ' ', sub_heading)
        sheet.write_number(7, col + 2, to_float(data['sale_total']),
                           total_amount_format)
        row = 8
        for sale in data['data']['sale']:
            if data['report_type']:
                if list(data['report_type'].keys())[0] == 'account':
                    if prev_account != sale['account']:
                        prev_account = sale['account']
                        sheet.write(row, col, sale['account'], txt_name)
                        sheet.write(row, col + 1, '', txt_name)
                        sheet.write(row, col + 2, '', txt_name)
                elif list(data['report_type'].keys())[0] == 'tax':
                    if prev_tax != sale['name']:
                        prev_tax = sale['name']
                        sheet.write(row, col, sale['name'] + '(' + str(
                            sale['amount']) + '%)', txt_name)
                        sheet.write(row, col + 1, '', txt_name)
                        sheet.write(row, col + 2, '', txt_name)
                row += 1
                if data['apply_comparison']:
                    if sale['dynamic net']:
                        periods = data['comparison_number_range']
                        for num in periods:
                            if sale['dynamic net'][
                                'dynamic_total_net_sum' + str(num)]:
                                sheet.write_number(row, col + j, to_float(
                                    sale['dynamic net'][
                                    'dynamic_total_net_sum' + str(num)]),
                                            amount_format)
                            if sale['dynamic tax'][
                                'dynamic_total_tax_sum' + str(num)]:
                                sheet.write_number(row, col, to_float(
                                    sale['dynamic tax'][
                                    'dynamic_total_tax_sum' + str(num)]),
                                            amount_format)
                            j += 1
                j = 0
                sheet.write(row, col + j, sale['name'], txt_name)
                sheet.write_number(row, col + j + 1, to_float(sale['net']),
                                   amount_format)
                sheet.write_number(row, col + j + 2, to_float(sale['tax']),
                                   amount_format)
            else:
                j = 0
                sheet.write(row, col + j, sale['name'], txt_name)
                sheet.write_number(row, col + j + 1, to_float(sale['net']),
                                   amount_format)
                sheet.write_number(row, col + j + 2, to_float(sale['tax']),
                                   amount_format)
                row += 1
        row += 1
        sheet.write(row, col, 'Purchase', sub_heading)
        sheet.write(row, col + 1, ' ', sub_heading)
        sheet.write_number(row, col + 2, to_float(data['purchase_total']),
                           total_amount_format)
        row += 1
        for purchase in data['data']['purchase']:
            if data['report_type']:
                if list(data['report_type'].keys())[0] == 'account':
                    if prev_account != purchase['account']:
                        prev_account = purchase['account']
                        sheet.write(row, col, purchase['account'], txt_name)
                        sheet.write(row, col + 1, '', txt_name)
                        sheet.write(row, col + 2, '', txt_name)
                elif list(data['report_type'].keys())[0] == 'tax':
                    if prev_tax != purchase['name']:
                        prev_tax = purchase['name']
                        sheet.write(row, col, purchase['name'] + '(' + str(
                            purchase['amount']) + '%)', txt_name)
                        sheet.write(row, col + 1, '', txt_name)
                        sheet.write(row, col + 2, '', txt_name)
                row += 1
                if data['apply_comparison']:
                    if purchase['dynamic net']:
                        periods = data['comparison_number_range']
                        for num in periods:
                            if purchase['dynamic net'][
                                'dynamic_total_net_sum' + str(num)]:
                                sheet.write_number(row, col + j, to_float(
                                            purchase['dynamic net'][
                                                'dynamic_total_net_sum' + str(
                                                    num)]),
                                            amount_format)
                            if purchase['dynamic tax'][
                                'dynamic_total_tax_sum' + str(num)]:
                                sheet.write_number(row, col, to_float(
                                    purchase['dynamic tax'][
                                    'dynamic_total_tax_sum' + str(num)]),
                                            amount_format)
                            j += 1
                j = 0
                sheet.write(row, col + j, purchase['name'], txt_name)
                sheet.write_number(row, col + j + 1, to_float(purchase['net']),
                                   amount_format)
                sheet.write_number(row, col + j + 2, to_float(purchase['tax']),
                                   amount_format)
            else:
                j = 0
                sheet.write(row, col + j, purchase['name'], txt_name)
                sheet.write_number(row, col + j + 1, to_float(purchase['net']),
                                   amount_format)
                sheet.write_number(row, col + j + 2, to_float(purchase['tax']),
                                   amount_format)
                row += 1
        row += 1
        sheet.write(row, col, 'Purchase', sub_heading)
        sheet.write(row, col + 1, ' ', sub_heading)
        sheet.write_number(row, col + 2, to_float(data['purchase_total']),
                           total_amount_format)
        row += 1
        workbook.close()
        output.seek(0)
        response.data = output.read()
        output.close()
