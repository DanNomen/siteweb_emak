# -*- coding: utf-8 -*-
import calendar
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DecadeStatement(models.Model):
    """Relevé par Décade — Batch de 10 jours groupant les factures par client."""
    _name = 'decade.statement'
    _description = 'Relevé par Décade'
    _order = 'date_start desc'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nom',
        required=True,
        readonly=True,
        default=lambda self: _('Nouveau'),
        tracking=True,
    )
    date_start = fields.Date(
        string='Date début',
        readonly=True,
        store=True,
    )
    date_end = fields.Date(
        string='Date fin',
        readonly=True,
        store=True,
    )
    month_ref = fields.Date(
        string='Mois de référence',
        default=lambda self: fields.Date.today().replace(day=1),
        help='Premier jour du mois concerné. Changez ce champ pour générer une décade sur un mois passé.',
    )
    decade_number = fields.Selection(
        selection=[
            ('1', 'Décade 1  (1 → 10)'),
            ('2', 'Décade 2  (11 → 20)'),
            ('3', 'Décade 3  (21 → fin du mois)'),
        ],
        string='Numéro de Décade',
        help='Choisir la décade — les dates se remplissent automatiquement.',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Brouillon'),
            ('ready', 'Prêt'),
            ('sent', 'Envoyé'),
        ],
        string='État',
        default='draft',
        required=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        comodel_name='decade.statement.line',
        inverse_name='statement_id',
        string='Clients',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Société',
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        readonly=True,
    )
    total_invoices = fields.Integer(
        string='Total Factures',
        compute='_compute_totals',
        store=True,
    )
    total_amount = fields.Monetary(
        string='Montant Total (TTC)',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    client_count = fields.Integer(
        string='Nb Clients',
        compute='_compute_totals',
        store=True,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Compute
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('line_ids', 'line_ids.total_amount', 'line_ids.invoice_count')
    def _compute_totals(self):
        for rec in self:
            rec.client_count = len(rec.line_ids)
            rec.total_invoices = sum(rec.line_ids.mapped('invoice_count'))
            rec.total_amount = sum(rec.line_ids.mapped('total_amount'))

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers statiques
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _get_decade_range(ref_date):
        """Retourne (date_start, date_end, decade_number) pour une date donnée."""
        day = ref_date.day
        year = ref_date.year
        month = ref_date.month
        last_day = calendar.monthrange(year, month)[1]

        if day <= 10:
            return ref_date.replace(day=1), ref_date.replace(day=10), 1
        elif day <= 20:
            return ref_date.replace(day=11), ref_date.replace(day=20), 2
        else:
            return ref_date.replace(day=21), ref_date.replace(day=last_day), 3

    @api.onchange('decade_number', 'month_ref')
    def _onchange_decade_number(self):
        """Auto-remplit date_start et date_end selon la décade et le mois choisis."""
        if not self.decade_number or not self.month_ref:
            return
        ref = self.month_ref
        year = ref.year
        month = ref.month
        last_day = calendar.monthrange(year, month)[1]
        if self.decade_number == '1':
            self.date_start = ref.replace(day=1)
            self.date_end = ref.replace(day=10)
        elif self.decade_number == '2':
            self.date_start = ref.replace(day=11)
            self.date_end = ref.replace(day=20)
        elif self.decade_number == '3':
            self.date_start = ref.replace(day=21)
            self.date_end = ref.replace(day=last_day)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('decade.statement') or _('Nouveau')
        return super().create(vals_list)

    # ─────────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────────

    def action_generate_lines(self):
        """Génère les lignes clients — filtre strict par période de la décade.
        Seules les factures dont la date est dans [date_start, date_end] sont incluses.
        """
        self.ensure_one()
        if not self.date_start or not self.date_end:
            raise UserError(_("Veuillez d'abord choisir un Numéro de Décade."))

        # Supprimer les lignes existantes avant régénération
        self.line_ids.unlink()

        # Factures non-payées de la période courante uniquement
        invoices = self.env['account.move'].search([
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', 'in', ['posted', 'draft']),
            ('payment_state', 'not in', ['paid', 'reversed']),
            ('invoice_date', '>=', self.date_start),
            ('invoice_date', '<=', self.date_end),
            ('partner_id', '!=', False),
            ('company_id', '=', self.company_id.id),
        ])

        if not invoices:
            raise UserError(_(
                "Aucune facture non-payée trouvée pour la période %s → %s."
            ) % (self.date_start, self.date_end))

        # Grouper par client et créer les lignes
        partners = invoices.mapped('partner_id')
        lines_vals = []
        for partner in partners:
            partner_invoices = invoices.filtered(
                lambda inv, p=partner: inv.partner_id == p
            )
            lines_vals.append({
                'statement_id': self.id,
                'partner_id': partner.id,
                'invoice_ids': [(6, 0, partner_invoices.ids)],
            })

        self.env['decade.statement.line'].create(lines_vals)
        self.state = 'ready'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Génération réussie'),
                'message': _(
                    '%d client(s) trouvé(s) avec %d facture(s) du %s au %s.'
                ) % (len(partners), len(invoices), self.date_start, self.date_end),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_send_all_emails(self):
        """Envoie les relevés par email à tous les clients du batch."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Générez d'abord les lignes clients."))

        sent_count = 0
        error_list = []
        for line in self.line_ids:
            if line.email_sent:
                continue
            if not line.partner_id.email:
                error_list.append(line.partner_id.name)
                continue
            try:
                line.action_send_email()
                sent_count += 1
            except Exception as e:
                _logger.error("Erreur envoi email pour %s : %s", line.partner_id.name, e)
                error_list.append(line.partner_id.name)

        if all(l.email_sent for l in self.line_ids):
            self.state = 'sent'

        msg = _('%d email(s) envoyé(s) avec succès.') % sent_count
        if error_list:
            msg += _(' Erreur pour : %s (email manquant ou invalide).') % ', '.join(error_list)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Envoi terminé'),
                'message': msg,
                'type': 'success' if not error_list else 'warning',
                'sticky': True,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_reset_to_draft(self):
        """Remet le relevé en brouillon pour permettre la régénération."""
        self.ensure_one()
        self.state = 'draft'

    # ─────────────────────────────────────────────────────────────────────────
    # Cron
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def _cron_generate_decade_statement(self):
        """Appelée automatiquement par le cron tous les 10 jours.
        Génère le batch décade pour la période courante.
        """
        today = fields.Date.today()
        date_start, date_end, decade_number = self._get_decade_range(today)
        # decade_number est maintenant une Selection string
        decade_number_str = str(decade_number)

        # Vérifier si ce batch existe déjà (pas de doublons)
        existing = self.search([
            ('date_start', '=', date_start),
            ('date_end', '=', date_end),
            ('company_id', '=', self.env.company.id),
        ])
        if existing:
            _logger.info(
                "Relevé Décade pour %s -> %s déjà existant — génération ignorée.", date_start, date_end
            )
            return

        _logger.info("Création automatique du relevé décade")

        statement = self.create({
            'date_start': date_start,
            'date_end': date_end,
            'month_ref': date_start.replace(day=1),
            'decade_number': decade_number_str,
            'state': 'draft',
        })

        try:
            statement.action_generate_lines()
            _logger.info(
                "Relevé '%s' généré — %d client(s), montant total : %s.",
                statement.name,
                statement.client_count,
                statement.total_amount,
            )
        except UserError as e:
            _logger.warning(
                "Relevé '%s' créé sans lignes (aucune facture) : %s", statement.name, str(e)
            )
