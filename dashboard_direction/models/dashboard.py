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


def _invoice_domain(company_id, move_types, date_from, date_to, extra=None):
    """Domaine de base pour chercher des factures/avoirs postés sur une
    période (move_types = ('out_invoice', 'out_refund') ou
    ('in_invoice', 'in_refund'))."""
    domain = [
        ('move_type', 'in', move_types),
        ('state', '=', 'posted'),
        ('company_id', '=', company_id),
        ('invoice_date', '>=', date_from),
        ('invoice_date', '<=', date_to),
    ]
    return domain + (extra or [])


def _net_amount(moves, invoice_type, amount_field):
    """Somme nette factures - avoirs : un avoir (facture d'achat) vient
    toujours en déduction du montant de la facture d'origine."""
    total = 0.0
    for move in moves:
        amount = getattr(move, amount_field)
        total += amount if move.move_type == invoice_type else -amount
    return total


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
    def _get_revenue(self, company_id, ref_date):
        cur_start, cur_end = _month_bounds(ref_date)
        prev_start, prev_end = _month_bounds(cur_start - timedelta(days=1))

        Move = self.env['account.move']
        move_types = ('out_invoice', 'out_refund')
        current = _net_amount(
            Move.search(_invoice_domain(company_id, move_types, cur_start, cur_end)),
            'out_invoice', 'amount_untaxed',
        )
        previous = _net_amount(
            Move.search(_invoice_domain(company_id, move_types, prev_start, prev_end)),
            'out_invoice', 'amount_untaxed',
        )

        return {
            'value': current,
            'evolution_pct': _pct_evolution(current, previous),
            'action': _action_def(
                'account.move',
                _invoice_domain(company_id, move_types, cur_start.isoformat(), cur_end.isoformat()),
                "Factures et avoirs clients - %s" % _month_label(cur_start),
            ),
        }

    # ---------------------------------------------------------------
    # 2. Marge brute (nécessite le module sale_margin)
    # ---------------------------------------------------------------
    @api.model
    def _get_gross_margin(self, company_id, ref_date):
        cur_start, cur_end = _month_bounds(ref_date)
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
    def _get_receivables(self, company_id, ref_date):
        cur_start, cur_end = _month_bounds(ref_date)
        prev_start, prev_end = _month_bounds(cur_start - timedelta(days=1))

        Move = self.env['account.move']
        move_types = ('out_invoice', 'out_refund')
        extra = [('payment_state', 'not in', ('paid', 'reversed'))]
        current = _net_amount(
            Move.search(_invoice_domain(company_id, move_types, cur_start, cur_end, extra)),
            'out_invoice', 'amount_residual',
        )
        previous = _net_amount(
            Move.search(_invoice_domain(company_id, move_types, prev_start, prev_end, extra)),
            'out_invoice', 'amount_residual',
        )

        return {
            'value': current,
            'evolution_pct': _pct_evolution(current, previous),
            'action': _action_def(
                'account.move',
                _invoice_domain(company_id, move_types, cur_start.isoformat(), cur_end.isoformat(), extra),
                "Créances clients - %s" % _month_label(cur_start),
            ),
        }

    # ---------------------------------------------------------------
    # 4. Recette mensuelle (journaux d'encaissement client sélectionnés)
    # ---------------------------------------------------------------
    # Noms des journaux (en minuscules) pris en compte pour la recette
    # mensuelle. Comparaison insensible à la casse : la base contient des
    # variantes ("Caisse principale" / "CAISSE PRINCIPALE").
    RECETTE_JOURNAL_NAMES = (
        'paiement par chèque du client',
        'virement effectué par le client',
        'paiement orange money',
        'caisse principale',
    )

    @api.model
    def _get_recette_journals(self, company_id):
        journals = self.env['account.journal'].search([
            ('type', 'in', ('cash', 'bank')),
            ('company_id', '=', company_id),
        ])
        return journals.filtered(
            lambda j: (j.name or '').strip().lower() in self.RECETTE_JOURNAL_NAMES
        )

    @api.model
    def _get_treasury(self, company_id, ref_date):
        cur_start, cur_end = _month_bounds(ref_date)
        prev_start, prev_end = _month_bounds(cur_start - timedelta(days=1))

        journals = self._get_recette_journals(company_id)
        # On récupère les montants comptabilisés sur le compte par défaut de
        # chaque journal (ex. 51510000 pour Orange Money), pas seulement les
        # écritures dont le journal_id correspond : certains encaissements
        # sur ce compte passent par d'autres journaux (rapprochement, OD...).
        account_ids = journals.mapped('default_account_id').ids
        domain_base = [
            ('account_id', 'in', account_ids),
            ('parent_state', '=', 'posted'),
        ]
        current = sum(self.env['account.move.line'].search(
            domain_base + [('date', '>=', cur_start), ('date', '<=', cur_end)]
        ).mapped('balance'))
        previous = sum(self.env['account.move.line'].search(
            domain_base + [('date', '>=', prev_start), ('date', '<=', prev_end)]
        ).mapped('balance'))

        return {
            'value': current,
            'evolution_pct': _pct_evolution(current, previous),
            'action': _action_def(
                'account.move.line',
                domain_base + [('date', '>=', cur_start.isoformat()), ('date', '<=', cur_end.isoformat())],
                "Recette mensuelle - %s" % _month_label(cur_start),
                view_mode='list',
            ),
        }

    # ---------------------------------------------------------------
    # 5. Valeur en stock (dernier snapshot vs mois précédent)
    # ---------------------------------------------------------------
    @api.model
    def _get_stock_value(self, company_id, ref_date):
        History = self.env['dashboard.stock.value.history']
        cur_start, cur_end = _month_bounds(ref_date)
        prev_start, prev_end = _month_bounds(cur_start - timedelta(days=1))
        is_current_month = cur_start == _month_bounds(date.today())[0]

        previous_snap = History.search([
            ('company_id', '=', company_id),
            ('snapshot_date', '>=', prev_start),
            ('snapshot_date', '<=', prev_end),
        ], order='snapshot_date desc', limit=1)

        if is_current_month:
            # Toujours calculée en direct (achat/vente/retour doivent se
            # répercuter immédiatement) : on ignore le snapshot du cron du
            # jour, qui ne sert qu'à figer l'historique une fois le mois clos.
            quants = self.env['stock.quant'].search([
                ('company_id', '=', company_id),
                ('location_id.usage', '=', 'internal'),
            ])
            current = sum(q.quantity * q.product_id.standard_price for q in quants)
        else:
            current_snap = History.search([
                ('company_id', '=', company_id),
                ('snapshot_date', '>=', cur_start),
                ('snapshot_date', '<=', cur_end),
            ], order='snapshot_date desc', limit=1)
            if not current_snap:
                # Mois passé sans snapshot enregistré : valeur non
                # reconstituable (le stock n'est pas un historique, seul un
                # snapshot en garde trace).
                return {
                    'value': None,
                    'action': _action_def(
                        'dashboard.stock.value.history',
                        [('company_id', '=', company_id)],
                        "Historique valeur du stock",
                    ),
                }
            current = current_snap.total_value

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
    def _get_purchases(self, company_id, ref_date):
        cur_start, cur_end = _month_bounds(ref_date)

        Move = self.env['account.move']
        move_types = ('in_invoice', 'in_refund')
        total = _net_amount(
            Move.search(_invoice_domain(company_id, move_types, cur_start, cur_end)),
            'in_invoice', 'amount_untaxed',
        )
        return {
            'value': total,
            'action': _action_def(
                'account.move',
                _invoice_domain(company_id, move_types, cur_start.isoformat(), cur_end.isoformat()),
                "Factures et avoirs fournisseurs - %s" % _month_label(cur_start),
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
    # 8. Top 5 produits vendus (30 derniers jours glissants, par valeur)
    # ---------------------------------------------------------------
    @api.model
    def _get_top_products(self, company_id):
        today = date.today()
        window_start = today - timedelta(days=30)
        lines = self.env['sale.order.line'].search([
            ('order_id.state', '=', 'sale'),
            ('order_id.company_id', '=', company_id),
            ('order_id.date_order', '>=', window_start),
            ('order_id.date_order', '<=', today),
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
            ('move_type', 'in', ('out_invoice', 'out_refund')),
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
            # Un avoir vient en déduction de la créance sur son propre panier
            # d'ancienneté (comme dans le rapport Odoo "Balance âgée").
            amount = move.amount_residual if move.move_type == 'out_invoice' else -move.amount_residual
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
            ('is_storable', '=', True),
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
    def get_all_kpis(self, company_id=None, target_month=None, target_year=None):
        company_id = company_id or self.env.company.id
        today = date.today()
        # ref_date pilote les 6 cartes KPI du haut (mois sélectionné dans le
        # tableau de bord) ; les autres sections (graphique, top produits,
        # ancienneté des créances, stock & appro) restent toujours "live".
        ref_date = date(target_year or today.year, target_month or today.month, 1)
        return {
            'revenue': self._get_revenue(company_id, ref_date),
            'gross_margin': self._get_gross_margin(company_id, ref_date),
            'receivables': self._get_receivables(company_id, ref_date),
            'treasury': self._get_treasury(company_id, ref_date),
            'stock_value': self._get_stock_value(company_id, ref_date),
            'purchases': self._get_purchases(company_id, ref_date),
            'revenue_evolution': self._get_revenue_evolution(company_id),
            'top_products': self._get_top_products(company_id),
            'receivables_aging': self._get_receivables_aging(company_id),
            'stock_status': self._get_stock_status(company_id),
            'currency_symbol': self.env.company.currency_id.symbol,
        }
