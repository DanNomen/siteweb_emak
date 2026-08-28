# -*- coding: utf-8 -*-
import calendar
import logging
from datetime import date, datetime, time, timedelta

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
    active = fields.Boolean(
        string='Actif',
        default=True,
        help="Décochez pour archiver ce relevé sans le supprimer.",
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
    invoice_detail_ids = fields.One2many(
        comodel_name='decade.statement.line.invoice',
        inverse_name='statement_id',
        string='Détail des Factures',
        help="Vue facture par facture (tous clients confondus), avec le relevé d'origine si repris d'une décade antérieure.",
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

    _sql_constraints = [
        (
            'unique_period_company',
            'unique(date_start, date_end, company_id)',
            "Un relevé existe déjà pour cette période et cette société.",
        ),
    ]

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
    def _compute_period(year, month, decade_number):
        """Retourne (date_start, date_end) pour un mois/décade donnés.
        decade_number : '1', '2' ou '3' (ou int équivalent).
        """
        last_day = calendar.monthrange(year, month)[1]
        decade_number = int(decade_number)
        if decade_number == 1:
            return date(year, month, 1), date(year, month, 10)
        elif decade_number == 2:
            return date(year, month, 11), date(year, month, 20)
        else:
            return date(year, month, 21), date(year, month, last_day)

    @classmethod
    def _get_decade_range(cls, ref_date):
        """Retourne (date_start, date_end, decade_number) pour une date donnée."""
        decade_number = 1 if ref_date.day <= 10 else (2 if ref_date.day <= 20 else 3)
        date_start, date_end = cls._compute_period(ref_date.year, ref_date.month, decade_number)
        return date_start, date_end, decade_number

    @classmethod
    def _get_closed_decade_for_date(cls, today):
        """Retourne (date_start, date_end, decade_number) pour la décade qui
        vient de se terminer la veille de `today`, ou None si `today` n'est
        pas un jour de bascule.

        Jours de bascule :
        - le 11 du mois -> décade 1 (1 -> 10) du mois courant vient de finir
        - le 21 du mois -> décade 2 (11 -> 20) du mois courant vient de finir
        - le 1er du mois -> décade 3 (21 -> fin) du mois PRÉCÉDENT vient de finir

        Utilisé par le cron quotidien : contrairement à un cron à intervalle
        fixe de 10 jours (qui dérape car les mois ne font pas tous 30 jours),
        vérifier le jour calendaire exact garantit un alignement correct sur
        toute l'année, y compris au passage d'une année à l'autre.
        """
        if today.day == 11:
            date_start, date_end = cls._compute_period(today.year, today.month, 1)
            return date_start, date_end, 1
        elif today.day == 21:
            date_start, date_end = cls._compute_period(today.year, today.month, 2)
            return date_start, date_end, 2
        elif today.day == 1:
            last_day_prev_month = today - timedelta(days=1)
            date_start, date_end = cls._compute_period(
                last_day_prev_month.year, last_day_prev_month.month, 3
            )
            return date_start, date_end, 3
        return None

    @api.onchange('decade_number', 'month_ref')
    def _onchange_decade_number(self):
        """Auto-remplit date_start et date_end selon la décade et le mois choisis."""
        if not self.decade_number or not self.month_ref:
            return
        self.date_start, self.date_end = self._compute_period(
            self.month_ref.year, self.month_ref.month, self.decade_number
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('decade.statement') or _('Nouveau')
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Impossible de supprimer le relevé '%s' : il n'est plus en brouillon. "
                    "Archivez-le plutôt si vous ne l'utilisez plus."
                ) % rec.name)
        return super().unlink()

    # ─────────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────────

    def _get_period_invoices_domain(self):
        """Domaine des factures clients non-payées, CUMULATIF jusqu'à la fin
        de la décade (pas seulement celles datées dans la période).

        Un relevé de décade doit refléter l'encours total du client à cette
        date : une facture de la décade 1 encore impayée doit réapparaître
        dans le relevé de la décade 3, avec un renvoi vers le relevé
        d'origine (voir DecadeStatementLine.get_invoices_origin_map, utilisé
        dans le rapport PDF). Sans le cumul, une facture ancienne impayée ne
        serait plus jamais reprise dans aucun relevé après sa décade
        d'émission.

        Inclut aussi les factures sans invoice_date (ex: brouillons créés
        hors formulaire) dont la date de création tombe avant la fin de la
        période, pour éviter qu'elles ne soient jamais reprises dans un relevé.
        """
        self.ensure_one()
        end_dt = datetime.combine(self.date_end, time.max)
        return [
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', 'in', ['posted', 'draft']),
            ('payment_state', 'not in', ['paid', 'reversed']),
            ('partner_id', '!=', False),
            ('company_id', '=', self.company_id.id),
            '|',
            ('invoice_date', '<=', self.date_end),
            '&', ('invoice_date', '=', False), ('create_date', '<=', end_dt),
        ]

    def action_generate_lines(self):
        """Génère les lignes clients avec l'encours cumulatif à la fin de la
        décade (voir _get_period_invoices_domain) : les factures d'une
        décade antérieure encore impayées sont reprises, avec un renvoi vers
        leur relevé d'origine sur le rapport PDF.

        Les lignes déjà envoyées (email_sent) sont conservées telles quelles
        (on ne perd pas la trace de ce qui a réellement été envoyé) ; seules
        les lignes non envoyées sont mises à jour ou recréées.
        """
        self.ensure_one()
        if not self.date_start or not self.date_end:
            raise UserError(_("Veuillez d'abord choisir un Numéro de Décade."))

        invoices = self.env['account.move'].search(self._get_period_invoices_domain())

        if not invoices and not self.line_ids:
            raise UserError(_(
                "Aucune facture non-payée trouvée à la date du %s."
            ) % self.date_end)

        partners = invoices.mapped('partner_id')
        existing_by_partner = {line.partner_id: line for line in self.line_ids}

        # Lignes dont le client n'a plus de facture dans la période : on ne les
        # retire que si l'email n'a pas déjà été envoyé (sinon on garde l'historique).
        obsolete_lines = self.line_ids.filtered(
            lambda l: l.partner_id not in partners and not l.email_sent
        )
        obsolete_lines.unlink()

        lines_to_create = []
        for partner in partners:
            partner_invoices = invoices.filtered(
                lambda inv, p=partner: inv.partner_id == p
            )
            line = existing_by_partner.get(partner)
            if line and not line.email_sent:
                line.invoice_ids = [(6, 0, partner_invoices.ids)]
            elif not line:
                lines_to_create.append({
                    'statement_id': self.id,
                    'partner_id': partner.id,
                    'invoice_ids': [(6, 0, partner_invoices.ids)],
                })
            # si line et line.email_sent : on ne touche pas à l'historique envoyé

        if lines_to_create:
            self.env['decade.statement.line'].create(lines_to_create)

        self.state = 'ready'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Génération réussie'),
                'message': _(
                    '%d client(s) trouvé(s) avec %d facture(s) en cours au %s.'
                ) % (len(partners), len(invoices), self.date_end),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_send_all_emails(self):
        """Met en file d'envoi les relevés par email pour tous les clients du batch.

        Les emails sont mis en queue (force_send=False) plutôt qu'envoyés de
        façon synchrone, pour ne pas bloquer l'interface sur un lot important
        de clients ; ils partent ensuite via le cron standard d'Odoo.
        """
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
                line.action_send_email(force_send=False)
                sent_count += 1
            except Exception:
                _logger.exception("Erreur envoi email pour %s", line.partner_id.name)
                error_list.append(line.partner_id.name)

        if all(l.email_sent for l in self.line_ids):
            self.state = 'sent'

        msg = _('%d email(s) mis en file d\'envoi avec succès.') % sent_count
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
    def _cron_generate_decade_statement(self, today=None):
        """Appelée automatiquement par le cron TOUS LES JOURS (voir
        data/decade_statement_cron.xml). Ne génère un relevé que le jour où
        une décade vient de se terminer (le 11, le 21, ou le 1er du mois) —
        voir _get_closed_decade_for_date(). Les autres jours, ne fait rien.

        Génère un relevé pour chaque société active (le cron tourne avec
        l'utilisateur technique, pas un utilisateur lié à une société en
        particulier).

        :param today: uniquement pour les tests, permet de simuler un jour
            de bascule précis sans dépendre de la date système.
        """
        today = today or fields.Date.today()
        decade_range = self._get_closed_decade_for_date(today)
        if not decade_range:
            return
        date_start, date_end, decade_number = decade_range
        decade_number_str = str(decade_number)

        for company in self.env['res.company'].search([]):
            existing = self.search([
                ('date_start', '=', date_start),
                ('date_end', '=', date_end),
                ('company_id', '=', company.id),
            ])
            if existing:
                _logger.info(
                    "Relevé Décade pour %s -> %s (société %s) déjà existant — génération ignorée.",
                    date_start, date_end, company.name,
                )
                continue

            _logger.info("Création automatique du relevé décade pour %s", company.name)

            statement = self.with_company(company).create({
                'date_start': date_start,
                'date_end': date_end,
                'month_ref': date_start.replace(day=1),
                'decade_number': decade_number_str,
                'state': 'draft',
                'company_id': company.id,
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
