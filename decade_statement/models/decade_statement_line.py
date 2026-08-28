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
    invoice_detail_ids = fields.One2many(
        comodel_name='decade.statement.line.invoice',
        inverse_name='line_id',
        string='Détail des Factures',
        help="Vue facture par facture (avec relevé d'origine), tenue synchronisée avec invoice_ids.",
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

    @api.depends(
        'invoice_ids', 'invoice_ids.amount_residual_signed', 'invoice_ids.currency_id', 'invoice_ids.state'
    )
    def _compute_invoice_totals(self):
        """Montant réellement dû (résiduel), pas le montant facturé initial.

        Important pour les factures reprises de décades antérieures : si un
        client a réglé partiellement une ancienne facture, seul le reliquat
        doit apparaître dans le nouveau relevé — pas le montant total d'origine.
        amount_residual_signed encode déjà le bon signe (positif pour une
        facture, négatif pour un avoir), donc pas besoin de logique manuelle
        par move_type ici (cohérent avec le calcul du rapport PDF).
        """
        for rec in self:
            invoices = rec.invoice_ids
            rec.invoice_count = len(invoices)
            target_currency = rec.currency_id or rec.env.company.currency_id
            total = 0.0
            for inv in invoices:
                amount = inv.amount_residual_signed
                if inv.currency_id and inv.currency_id != target_currency:
                    amount = inv.currency_id._convert(
                        amount, target_currency, inv.company_id, inv.invoice_date or fields.Date.today()
                    )
                total += amount
            rec.total_amount = total

    # ─────────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────────

    def unlink(self):
        for line in self:
            if line.email_sent:
                raise UserError(_(
                    "Impossible de supprimer la ligne de '%s' : l'email a déjà été envoyé."
                ) % line.partner_id.name)
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._sync_invoice_details()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'invoice_ids' in vals:
            self._sync_invoice_details()
        return res

    def _sync_invoice_details(self):
        """Garde decade.statement.line.invoice aligné sur invoice_ids, pour
        pouvoir afficher chaque facture individuellement (avec son relevé
        d'origine) sans changer le fonctionnement de invoice_ids ailleurs
        (rapport PDF, template email, action_generate_lines...).

        Exécuté en sudo : c'est un modèle de bookkeeping interne, l'utilisateur
        n'a pas besoin de droits dessus pour que la synchronisation fonctionne.
        """
        Detail = self.env['decade.statement.line.invoice'].sudo()
        for line in self:
            existing = Detail.search([('line_id', '=', line.id)])
            existing_invoice_ids = set(existing.mapped('invoice_id').ids)
            wanted_ids = set(line.invoice_ids.ids)

            # Important : calculer existing_invoice_ids AVANT l'unlink — un
            # recordset ne doit plus être touché après suppression de ses
            # enregistrements (MissingError).
            existing.filtered(lambda d: d.invoice_id.id not in wanted_ids).unlink()

            for invoice_id in wanted_ids - existing_invoice_ids:
                Detail.create({'line_id': line.id, 'invoice_id': invoice_id})

    def action_send_email(self, force_send=True):
        """Envoie le relevé par email au client.

        :param force_send: si True (envoi manuel unitaire), l'email part
            immédiatement et le résultat est connu tout de suite. Si False
            (envoi en masse), l'email est simplement mis en file d'attente
            pour ne pas bloquer l'interface sur un lot de clients.
        """
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

        template.send_mail(self.id, force_send=force_send)

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

    def get_invoices_origin_map(self):
        """Pour chaque facture de la ligne, cherche si elle figurait déjà dans
        un relevé antérieur. Retourne un dict {invoice_id: nom_du_relevé_ou_texte}.

        Version batchée (une seule requête pour toutes les factures de la
        ligne) destinée au rapport PDF, qui itère sur les factures : appeler
        get_invoice_origin_statement() dans une boucle ferait une requête SQL
        par facture.
        """
        self.ensure_one()
        invoices = self.invoice_ids
        result = {}
        if not invoices:
            return result

        older_lines = self.env['decade.statement.line'].search([
            ('invoice_ids', 'in', invoices.ids),
            ('statement_id.date_start', '<', self.statement_id.date_start),
            ('statement_id.state', '!=', 'draft'),
            ('id', '!=', self.id),
        ])

        for invoice in invoices:
            matching_lines = older_lines.filtered(lambda l, inv=invoice: inv in l.invoice_ids)
            if matching_lines:
                matching_lines = matching_lines.sorted(key=lambda l: l.statement_id.date_start)
                result[invoice.id] = matching_lines[0].statement_id.name
            elif invoice.invoice_date and invoice.invoice_date < self.statement_id.date_start:
                result[invoice.id] = "Période antérieure"

        return result

    def get_invoice_origin_statement(self, invoice):
        """Cherche si une facture figurait déjà dans un ancien relevé.
        Retourne le nom du relevé d'origine (ex: 'Décade 1 - Août 2026') ou False.

        Conservée pour un usage ponctuel (une seule facture) ; pour itérer sur
        plusieurs factures, préférer get_invoices_origin_map() qui évite le
        problème N+1 requêtes.
        """
        self.ensure_one()
        return self.get_invoices_origin_map().get(invoice.id, False)
