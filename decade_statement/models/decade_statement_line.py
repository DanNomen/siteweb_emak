# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DecadeStatementLine(models.Model):
    """Ligne d'un relevé décadaire — un client et l'ensemble de ses factures."""
    _name = 'decade.statement.line'
    _description = 'Ligne Relevé par Décade'
    _order = 'partner_id'

    statement_id = fields.Many2one(
        comodel_name='decade.statement',
        string='Relevé Décade',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Client',
        required=True,
        index=True,
    )
    partner_email = fields.Char(
        string='Email',
        related='partner_id.email',
        readonly=True,
    )
    invoice_ids = fields.Many2many(
        comodel_name='account.move',
        relation='decade_statement_line_invoice_rel',
        column1='line_id',
        column2='invoice_id',
        string='Factures',
        domain=[('move_type', 'in', ['out_invoice', 'out_refund'])],
    )
    invoice_count = fields.Integer(
        string='Nb Factures',
        compute='_compute_invoice_totals',
        store=True,
    )
    total_amount = fields.Monetary(
        string='Montant Total (TTC)',
        compute='_compute_invoice_totals',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='statement_id.currency_id',
        readonly=True,
    )
    email_sent = fields.Boolean(
        string='Email Envoyé',
        default=False,
    )
    email_sent_date = fields.Datetime(
        string='Date Envoi',
        readonly=True,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Compute
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('invoice_ids', 'invoice_ids.amount_total', 'invoice_ids.state')
    def _compute_invoice_totals(self):
        for rec in self:
            invoices = rec.invoice_ids
            rec.invoice_count = len(invoices)
            total = 0.0
            for inv in invoices:
                # Avoirs : on soustrait
                if inv.move_type == 'out_invoice':
                    total += inv.amount_total
                elif inv.move_type == 'out_refund':
                    total -= inv.amount_total
            rec.total_amount = total

    # ─────────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────────

    def action_send_email(self):
        """Envoie le relevé par email au client."""
        self.ensure_one()

        if not self.partner_id.email:
            raise UserError(_(
                "Le client '%s' n'a pas d'adresse email configurée."
            ) % self.partner_id.name)

        if not self.invoice_ids:
            raise UserError(_(
                "Aucune facture à envoyer pour '%s'."
            ) % self.partner_id.name)

        template = self.env.ref(
            'decade_statement.email_template_decade_statement',
            raise_if_not_found=False,
        )
        if not template:
            raise UserError(_(
                "Template email introuvable. Veuillez réinstaller le module."
            ))

        template.send_mail(self.id, force_send=True)

        self.write({
            'email_sent': True,
            'email_sent_date': fields.Datetime.now(),
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Email envoyé'),
                'message': _(
                    'Relevé envoyé à %s (%s).'
                ) % (self.partner_id.name, self.partner_id.email),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_view_invoices(self):
        """Ouvre la liste des factures du client pour cette décade."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Factures — %s') % self.partner_id.name,
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
            'context': {'default_move_type': 'out_invoice'},
        }

    def get_invoice_origin_statement(self, invoice):
        """Cherche si la facture figurait déjà dans un ancien relevé.
        Retourne le nom du relevé d'origine (ex: 'Décade 1 - Août 2026') ou False.
        """
        self.ensure_one()
        # Chercher les autres lignes de relevés contenant cette facture
        # qui appartiennent à un relevé dont la date de début est antérieure à celui-ci
        older_lines = self.env['decade.statement.line'].search([
            ('invoice_ids', 'in', invoice.id),
            ('statement_id.date_start', '<', self.statement_id.date_start),
            ('statement_id.state', '!=', 'draft'), # Idéalement que les relevés confirmés/envoyés
        ])
        
        if older_lines:
            older_lines = older_lines.sorted(key=lambda l: l.statement_id.date_start)
            return older_lines[0].statement_id.name
        
        # Si on ne trouve pas de relevé antérieur, on vérifie si la facture date d'avant
        # le début de cette décade (facture antérieure à l'utilisation du module)
        if invoice.invoice_date and invoice.invoice_date < self.statement_id.date_start:
            return "Période antérieure"
            
        return False
