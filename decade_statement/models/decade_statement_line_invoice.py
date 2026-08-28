# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DecadeStatementLineInvoice(models.Model):
    """Détail facture par facture d'une ligne de relevé — permet d'afficher
    chaque facture individuellement (au lieu du seul total agrégé par
    client) avec, le cas échéant, le relevé où elle est apparue pour la
    première fois. Tenu synchronisé automatiquement avec
    decade.statement.line.invoice_ids (voir DecadeStatementLine._sync_invoice_details) —
    ce n'est pas un modèle à éditer à la main.
    """
    _name = 'decade.statement.line.invoice'
    _description = 'Détail Facture — Relevé par Décade'
    _order = 'invoice_date, id'

    line_id = fields.Many2one(
        comodel_name='decade.statement.line',
        string='Ligne Relevé',
        required=True,
        ondelete='cascade',
        index=True,
    )
    statement_id = fields.Many2one(
        comodel_name='decade.statement',
        related='line_id.statement_id',
        store=True,
        readonly=True,
        string='Relevé',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        related='line_id.partner_id',
        store=True,
        readonly=True,
        string='Client',
    )
    invoice_id = fields.Many2one(
        comodel_name='account.move',
        string='Facture',
        required=True,
        ondelete='cascade',
        index=True,
    )
    invoice_date = fields.Date(related='invoice_id.invoice_date', store=True, readonly=True)
    invoice_date_due = fields.Date(related='invoice_id.invoice_date_due', readonly=True)
    move_state = fields.Selection(related='invoice_id.state', readonly=True, string='État')
    amount_residual_signed = fields.Monetary(
        related='invoice_id.amount_residual_signed', readonly=True, string='Montant dû',
    )
    currency_id = fields.Many2one(related='invoice_id.currency_id', readonly=True)
    origin_statement_id = fields.Many2one(
        comodel_name='decade.statement',
        compute='_compute_origin_statement_id',
        store=True,
        readonly=True,
        string="Relevé d'origine",
        help=(
            "Relevé antérieur dans lequel cette facture était déjà présente "
            "(facture encore impayée reprise d'une décade précédente). "
            "Vide si la facture apparaît pour la première fois dans ce relevé."
        ),
    )
    is_new_this_period = fields.Boolean(
        compute='_compute_is_new_this_period',
        store=True,
        readonly=True,
        string='Nouvelle cette décade',
        help=(
            "Coché si la facture est datée dans la période [Date début, Date fin] "
            "de ce relevé. Décoché si elle a été reprise d'une décade antérieure "
            "encore impayée (voir Relevé d'origine)."
        ),
    )

    _sql_constraints = [
        (
            'unique_line_invoice',
            'unique(line_id, invoice_id)',
            "Cette facture est déjà présente sur cette ligne de relevé.",
        ),
    ]

    @api.depends('invoice_id', 'line_id.statement_id')
    def _compute_origin_statement_id(self):
        for rec in self:
            rec.origin_statement_id = False
            if not rec.invoice_id or not rec.statement_id:
                continue
            older = self.search([
                ('invoice_id', '=', rec.invoice_id.id),
                ('statement_id.date_start', '<', rec.statement_id.date_start),
                ('statement_id.state', '!=', 'draft'),
                ('id', '!=', rec.id),
            ])
            if older:
                older = older.sorted(key=lambda r: r.statement_id.date_start)
                rec.origin_statement_id = older[0].statement_id

    @api.depends('invoice_date', 'statement_id.date_start', 'statement_id.date_end')
    def _compute_is_new_this_period(self):
        for rec in self:
            statement = rec.statement_id
            rec.is_new_this_period = bool(
                rec.invoice_date and statement.date_start and statement.date_end
                and statement.date_start <= rec.invoice_date <= statement.date_end
            )
