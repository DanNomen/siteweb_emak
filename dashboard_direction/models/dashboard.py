# -*- coding: utf-8 -*-
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo import models, api


def _month_bounds(ref_date):
    """Retourne (premier_jour, dernier_jour) du mois de ref_date."""
    first = ref_date.replace(day=1)
    last = first + relativedelta(months=1, days=-1)
    return first, last


def _pct_evolution(current, previous):
    if not previous:
        return 100.0 if current else 0.0
    return round((current - previous) / abs(previous) * 100, 2)


FR_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _month_label(d):
    """Libellé FR indépendant de la locale serveur (contrairement à strftime)."""
    return "%s %s" % (FR_MONTHS[d.month - 1], d.year)


def _action_def(res_model, domain, name, view_mode='list,form'):
    """Définition minimale d'un ir.actions.act_window, prête à être
    envoyée telle quelle au client (dates converties en chaînes ISO,
    seul format accepté dans un domaine transmis en JSON)."""
    return {
        'res_model': res_model,
        'domain': domain,
        'name': name,
        'view_mode': view_mode,
    }


class DashboardDirection(models.AbstractModel):
    """Modèle transient (pas de table) : sert uniquement de point d'entrée
    RPC pour agréger les KPI. Aucune donnée n'est stockée ici, sauf
    dashboard.stock.value.history qui nécessite un historique réel."""
    _name = 'dashboard.direction'
    _description = "Agrégateur KPI Tableau de Bord Direction"

    # ---------------------------------------------------------------
    # 1. Chiffre d'affaires
    # ---------------------------------------------------------------
    @api.model
    def _get_revenue(self, company_id):
        today = date.today()
        cur_start, cur_end = _month_bounds(today)
        prev_start, prev_end = _month_bounds(cur_start - timedelta(days=1))

        Move = self.env['account.move']
        domain_base = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('company_id', '=', company_id),
        ]
        cur_domain = domain_base + [('invoice_date', '>=', cur_start), ('invoice_date', '<=', cur_end)]
        current = sum(Move.search(cur_domain).mapped('amount_untaxed'))
        previous = sum(Move.search(
            domain_base + [('invoice_date', '>=', prev_start), ('invoice_date', '<=', prev_end)]
        ).mapped('amount_untaxed'))

        return {
            'value': current,
            'evolution_pct': _pct_evolution(current, previous),
            'action': _action_def(
                'account.move',
                domain_base + [('invoice_date', '>=', cur_start.isoformat()), ('invoice_date', '<=', cur_end.isoformat())],
                "Factures clients - %s" % _month_label(cur_start),
            ),
        }

    # ---------------------------------------------------------------
    # 2. Marge brute (nécessite le module sale_margin)
    # ---------------------------------------------------------------
    @api.model
    def _get_gross_margin(self, company_id):
        today = date.today()
        cur_start, cur_end = _month_bounds(today)
        prev_start, prev_end = _month_bounds(cur_start - timedelta(days=1))

        Order = self.env['sale.order']
        domain_base = [
            ('state', '=', 'sale'),
            ('company_id', '=', company_id),
        ]
        current = sum(Order.search(
            domain_base + [('date_order', '>=', cur_start), ('date_order', '<=', cur_end)]
        ).mapped('margin'))
        previous = sum(Order.search(
            domain_base + [('date_order', '>=', prev_start), ('date_order', '<=', prev_end)]
        ).mapped('margin'))

        return {
            'value': current,
            'evolution_pct': _pct_evolution(current, previous),
            'action': _action_def(
                'sale.order',
                domain_base + [('date_order', '>=', cur_start.isoformat()), ('date_order', '<=', cur_end.isoformat())],
                "Commandes - %s" % _month_label(cur_start),
            ),
        }

    # ---------------------------------------------------------------
    # 3. Créances clients (factures du mois non soldées)
    # ---------------------------------------------------------------
    @api.model
    def _get_receivables(self, company_id):
        today = date.today()
        cur_start, cur_end = _month_bounds(today)
        prev_start, prev_end = _month_bounds(cur_start - timedelta(days=1))

        Move = self.env['account.move']
        domain_base = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ('paid', 'reversed')),
            ('company_id', '=', company_id),
        ]
        current = sum(Move.search(
            domain_base + [('invoice_date', '>=', cur_start), ('invoice_date', '<=', cur_end)]
        ).mapped('amount_residual'))
        previous = sum(Move.search(
            domain_base + [('invoice_date', '>=', prev_start), ('invoice_date', '<=', prev_end)]
        ).mapped('amount_residual'))

        return {
            'value': current,
            'evolution_pct': _pct_evolution(current, previous),
            'action': _action_def(
                'account.move',
                domain_base + [('invoice_date', '>=', cur_start.isoformat()), ('invoice_date', '<=', cur_end.isoformat())],
                "Créances clients - %s" % _month_label(cur_start),
            ),
        }

    # ---------------------------------------------------------------
    # 4. Trésorerie (journaux espèces + banque)
    # ---------------------------------------------------------------
    @api.model
    def _get_treasury(self, company_id):
        journals = self.env['account.journal'].search([
            ('type', 'in', ('cash', 'bank')),
            ('company_id', '=', company_id),
        ])
        account_ids = journals.default_account_id.ids
        total = 0.0
        for journal in journals:
            account = journal.default_account_id
            if account:
                lines = self.env['account.move.line'].search([
                    ('account_id', '=', account.id),
                    ('parent_state', '=', 'posted'),
                ])
                total += sum(lines.mapped('balance'))
        return {
            'value': total,
            'action': _action_def(
                'account.move.line',
                [('account_id', 'in', account_ids), ('parent_state', '=', 'posted')],
                "Écritures trésorerie",
                view_mode='list',
            ),
        }

    # ---------------------------------------------------------------
    # 5. Valeur en stock (dernier snapshot vs mois précédent)
    # ---------------------------------------------------------------
    @api.model
    def _get_stock_value(self, company_id):
        History = self.env['dashboard.stock.value.history']
        today = date.today()
        cur_start, _ = _month_bounds(today)
        prev_start, prev_end = _month_bounds(cur_start - timedelta(days=1))

        current_snap = History.search([
            ('company_id', '=', company_id),
            ('snapshot_date', '>=', cur_start),
        ], order='snapshot_date desc', limit=1)
        previous_snap = History.search([
            ('company_id', '=', company_id),
            ('snapshot_date', '>=', prev_start),
            ('snapshot_date', '<=', prev_end),
        ], order='snapshot_date desc', limit=1)

        current = current_snap.total_value if current_snap else 0.0
        previous = previous_snap.total_value if previous_snap else 0.0
        return {
            'value': current,
            'evolution_pct': _pct_evolution(current, previous),
            'action': _action_def(
                'dashboard.stock.value.history',
                [('company_id', '=', company_id)],
                "Historique valeur du stock",
            ),
        }

    # ---------------------------------------------------------------
    # 6. Achats du mois
    # ---------------------------------------------------------------
    @api.model
    def _get_purchases(self, company_id):
        today = date.today()
        cur_start, cur_end = _month_bounds(today)

        Move = self.env['account.move']
        domain_base = [
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('company_id', '=', company_id),
        ]
        total = sum(Move.search(
            domain_base + [('invoice_date', '>=', cur_start), ('invoice_date', '<=', cur_end)]
        ).mapped('amount_untaxed'))
        return {
            'value': total,
            'action': _action_def(
                'account.move',
                domain_base + [('invoice_date', '>=', cur_start.isoformat()), ('invoice_date', '<=', cur_end.isoformat())],
                "Factures fournisseurs - %s" % _month_label(cur_start),
            ),
        }

    # ---------------------------------------------------------------
    # 7. Évolution du CA sur 12 mois (reset chaque année civile)
    # ---------------------------------------------------------------
    @api.model
    def _get_revenue_evolution(self, company_id):
        today = date.today()
        year_start = today.replace(month=1, day=1)
        Move = self.env['account.move']
        result = []
        for m in range(1, 13):
            month_start = year_start.replace(month=m)
            month_end = _month_bounds(month_start)[1]
            if month_start > today:
                result.append({'month': m, 'value': 0.0})
                continue
            total = sum(Move.search([
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('company_id', '=', company_id),
                ('invoice_date', '>=', month_start),
                ('invoice_date', '<=', month_end),
            ]).mapped('amount_untaxed'))
            result.append({'month': m, 'value': total})
        return result

    # ---------------------------------------------------------------
    # 8. Top 5 produits vendus (mois en cours, par valeur)
    # ---------------------------------------------------------------
    @api.model
    def _get_top_products(self, company_id):
        today = date.today()
        cur_start, cur_end = _month_bounds(today)
        lines = self.env['sale.order.line'].search([
            ('order_id.state', '=', 'sale'),
            ('order_id.company_id', '=', company_id),
            ('order_id.date_order', '>=', cur_start),
            ('order_id.date_order', '<=', cur_end),
        ])
        grouped = {}
        for line in lines:
            key = line.product_id
            if not key:
                continue
            grouped.setdefault(key, {'qty': 0.0, 'value': 0.0})
            grouped[key]['qty'] += line.product_uom_qty
            grouped[key]['value'] += line.price_subtotal
        ranked = sorted(grouped.items(), key=lambda kv: kv[1]['value'], reverse=True)[:5]
        return [
            {'product': p.display_name, 'qty': v['qty'], 'value': v['value'], 'product_id': p.id}
            for p, v in ranked
        ]

    # ---------------------------------------------------------------
    # 9. Créances par ancienneté
    # ---------------------------------------------------------------
    @api.model
    def _get_receivables_aging(self, company_id):
        today = date.today()
        moves = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ('paid', 'reversed')),
            ('company_id', '=', company_id),
        ])
        buckets = {'0_30': 0.0, '31_60': 0.0, '61_90': 0.0, '90_plus': 0.0}
        move_ids = {'0_30': [], '31_60': [], '61_90': [], '90_plus': []}
        for move in moves:
            due = move.invoice_date_due or move.invoice_date
            if not due:
                continue
            days_overdue = (today - due).days
            amount = move.amount_residual
            if days_overdue <= 30:
                key = '0_30'
            elif days_overdue <= 60:
                key = '31_60'
            elif days_overdue <= 90:
                key = '61_90'
            else:
                key = '90_plus'
            buckets[key] += amount
            move_ids[key].append(move.id)

        bucket_names = {
            '0_30': "Créances 0-30 jours",
            '31_60': "Créances 31-60 jours",
            '61_90': "Créances 61-90 jours",
            '90_plus': "Créances 90 jours et plus",
        }
        buckets['actions'] = {
            key: _action_def('account.move', [('id', 'in', ids)], bucket_names[key])
            for key, ids in move_ids.items()
        }
        return buckets

    # ---------------------------------------------------------------
    # 10. Stock et appro
    # ---------------------------------------------------------------
    @api.model
    def _get_stock_status(self, company_id):
        Product = self.env['product.product']

        # Basé sur qty_available (comme le filtre "Quantité disponible >= 1"
        # de la vue Produits), et non sur le nombre de quants : un même
        # produit réparti sur plusieurs lots/emplacements ne doit être
        # compté qu'une seule fois.
        domain_base = [
            ('type', '=', 'product'),
            ('company_id', 'in', (company_id, False)),
        ]
        in_stock = Product.search_count(domain_base + [('qty_available', '>', 0)])
        out_of_stock = Product.search_count(domain_base + [('qty_available', '<=', 0)])

        today = date.today()
        lots = self.env['stock.lot'].search([
            ('company_id', '=', company_id),
            ('expiration_date', '!=', False),
            ('expiration_date', '>=', today),
        ])
        expiry_3m = today + relativedelta(months=3)
        expiry_6m = today + relativedelta(months=6)
        expiry_12m = today + relativedelta(months=12)

        buckets = {'0_3m': 0, '3_6m': 0, '6_12m': 0}
        lot_ids = {'0_3m': [], '3_6m': [], '6_12m': []}
        for lot in lots:
            exp = lot.expiration_date.date() if hasattr(lot.expiration_date, 'date') else lot.expiration_date
            if exp <= expiry_3m:
                key = '0_3m'
            elif exp <= expiry_6m:
                key = '3_6m'
            elif exp <= expiry_12m:
                key = '6_12m'
            else:
                continue
            buckets[key] += 1
            lot_ids[key].append(lot.id)

        return {
            'in_stock_count': in_stock,
            'out_of_stock_count': out_of_stock,
            'expiring': buckets,
            'actions': {
                'in_stock': _action_def('product.product', domain_base + [('qty_available', '>', 0)], "Produits disponibles"),
                'out_of_stock': _action_def('product.product', domain_base + [('qty_available', '<=', 0)], "Ruptures de stock"),
                'expiring_0_3m': _action_def('stock.lot', [('id', 'in', lot_ids['0_3m'])], "Péremption < 3 mois"),
                'expiring_3_12m': _action_def('stock.lot', [('id', 'in', lot_ids['3_6m'] + lot_ids['6_12m'])], "Péremption 3-12 mois"),
            },
        }

    # ---------------------------------------------------------------
    # Point d'entrée unique : agrège tout en un seul appel RPC
    # ---------------------------------------------------------------
    @api.model
    def get_all_kpis(self, company_id=None):
        company_id = company_id or self.env.company.id
        return {
            'revenue': self._get_revenue(company_id),
            'gross_margin': self._get_gross_margin(company_id),
            'receivables': self._get_receivables(company_id),
            'treasury': self._get_treasury(company_id),
            'stock_value': self._get_stock_value(company_id),
            'purchases': self._get_purchases(company_id),
            'revenue_evolution': self._get_revenue_evolution(company_id),
            'top_products': self._get_top_products(company_id),
            'receivables_aging': self._get_receivables_aging(company_id),
            'stock_status': self._get_stock_status(company_id),
            'currency_symbol': self.env.company.currency_id.symbol,
        }
