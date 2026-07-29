# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMergeLog(models.Model):
    """Journal d'audit : une ligne par fusion réellement exécutée.
    Sert de preuve/traçabilité en cas de contrôle comptable ou fiscal.
    """
    _name = 'account.merge.log'
    _description = "Journal d'audit des fusions de comptes"
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)

    wizard_reference = fields.Char(string="Référence wizard", help="ID technique du wizard ayant déclenché la fusion")
    source_account_ids = fields.Many2many(
        'account.account', string="Compte(s) source",
        help="Comptes vidés lors de la fusion"
    )
    destination_account_id = fields.Many2one(
        'account.account', string="Compte destination",
        help="Compte cible principal (optionnel, peut varier selon les groupes)"
    )
    partner_id = fields.Many2one('res.partner', string="Client concerné")
    company_id = fields.Many2one('res.company', string="Société", default=lambda self: self.env.company)

    line_count = fields.Integer(string="Nombre de pièces transférées")
    balance_before_source = fields.Monetary(string="Solde source avant", currency_field='currency_id')
    balance_after_destination = fields.Monetary(string="Solde destination après", currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    state = fields.Selection([
        ('dry_run', 'Simulation (dry-run)'),
        ('done', 'Fusion exécutée'),
        ('failed', 'Échec / Rollback'),
    ], string="Statut", default='dry_run', required=True)

    error_message = fields.Text(string="Message d'erreur (si échec)")
    executed_by = fields.Many2one('res.users', string="Exécuté par", default=lambda self: self.env.user)
    notes = fields.Text(string="Notes")

    @api.depends('destination_account_id', 'partner_id', 'state', 'create_date')
    def _compute_display_name(self):
        for rec in self:
            partner = rec.partner_id.name or '—'
            dest = rec.destination_account_id.code if rec.destination_account_id else '—'
            rec.display_name = f"[{rec.state}] {partner} -> {dest} ({rec.line_count} pièces)"
