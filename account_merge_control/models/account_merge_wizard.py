# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMergeWizard(models.TransientModel):
    _inherit = 'account.merge.wizard'

    # -------------------------------------------------------------------
    # NOUVEAUX CHAMPS DE CONTRÔLE
    # -------------------------------------------------------------------
    dry_run = fields.Boolean(
        string="Mode simulation (dry-run)",
        default=True,
        help="Si coché : calcule et affiche l'impact SANS rien écrire en base. "
             "Décochez uniquement après avoir vérifié l'aperçu."
    )
    preview_line_count = fields.Integer(string="Nb pièces à transférer", readonly=True)
    preview_balance = fields.Monetary(
        string="Solde total concerné",
        readonly=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    ignore_lock_date_check = fields.Boolean(
        string="Forcer même si période verrouillée",
        default=False,
        help="Dangereux : à cocher uniquement en connaissance de cause, "
             "casse potentiellement le hash d'inaltérabilité si activé.",
    )
    confirmation_text = fields.Char(
        string="Tapez CONFIRMER pour valider",
        help="Sécurité anti-clic-accidentel sur un volume important de pièces.",
    )

    # -------------------------------------------------------------------
    # HELPERS : récupère les comptes source sélectionnés et la cible
    # -------------------------------------------------------------------
    def _get_selected_source_accounts(self):
        """Retourne les comptes sélectionnés (hors premier de chaque groupe).

        Dans la logique native, le premier compte d'un groupe devient la
        destination ; les suivants sont les sources à fusionner vers lui.
        On renvoie ici TOUS les comptes sélectionnés pour le calcul du
        preview (balance des pièces à déplacer).
        """
        self.ensure_one()
        selected_lines = self.wizard_line_ids.filtered(
            lambda l: l.display_type == 'account' and l.is_selected and not l.info
        )
        # Regroupe par clé de groupe ; dans chaque groupe le 1er = destination
        sources = self.env['account.account']
        for group_lines in selected_lines.grouped('grouping_key').values():
            sorted_lines = group_lines.sorted('sequence')
            if len(sorted_lines) > 1:
                # Les comptes source sont ceux après le premier (la destination)
                sources |= sorted_lines[1:].account_id
        return sources

    def _get_all_selected_accounts(self):
        """Retourne tous les comptes des lignes sélectionnées (toutes positions)."""
        self.ensure_one()
        selected_lines = self.wizard_line_ids.filtered(
            lambda l: l.display_type == 'account' and l.is_selected and not l.info
        )
        return selected_lines.account_id

    # -------------------------------------------------------------------
    # ACTION APERÇU (dry-run)
    # -------------------------------------------------------------------
    def action_preview(self):
        """Calcule l'impact de la fusion sans rien modifier."""
        self.ensure_one()
        sources = self._get_selected_source_accounts()
        if not sources:
            raise UserError(_(
                "Aucun compte source à fusionner. Sélectionnez au moins 2 comptes "
                "dans un même groupe."
            ))

        lines = self.env['account.move.line'].search([('account_id', 'in', sources.ids)])
        total_balance = sum(lines.mapped('balance'))

        self.preview_line_count = len(lines)
        self.preview_balance = total_balance

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Aperçu de la fusion"),
                'message': _(
                    "%(count)s pièces comptables seront transférées depuis les comptes source.\n"
                    "Solde total concerné : %(balance)s %(currency)s"
                ) % {
                    'count': self.preview_line_count,
                    'balance': self.preview_balance,
                    'currency': self.currency_id.name or '',
                },
                'sticky': True,
            }
        }

    # -------------------------------------------------------------------
    # VÉRIFICATION PÉRIODES VERROUILLÉES
    # -------------------------------------------------------------------
    def _check_locked_periods(self, accounts):
        """Bloque si des écritures sont dans une période verrouillée,
        sauf si l'utilisateur force explicitement."""
        if self.ignore_lock_date_check:
            return
        company = self.env.company
        lock_date = company.fiscalyear_lock_date or company.period_lock_date
        if not lock_date:
            return
        locked_lines = self.env['account.move.line'].search([
            ('account_id', 'in', accounts.ids),
            ('date', '<=', lock_date),
        ], limit=1)
        if locked_lines:
            raise UserError(_(
                "Des écritures antérieures à la date de verrouillage (%(lock)s) "
                "existent sur le(s) compte(s) source. Fusion bloquée par sécurité. "
                "Cochez 'Forcer même si période verrouillée' uniquement si vous "
                "savez ce que vous faites."
            ) % {'lock': lock_date})

    # -------------------------------------------------------------------
    # SURCHARGE action_merge : contrôles + dry-run + savepoint + audit
    # -------------------------------------------------------------------
    def action_merge(self):
        """Point d'entrée surchargé : ajoute contrôles, dry-run, savepoint et audit."""
        self.ensure_one()

        sources = self._get_selected_source_accounts()
        all_selected = self._get_all_selected_accounts()

        if not all_selected:
            raise UserError(_(
                "Aucun compte sélectionné. Sélectionnez au moins 2 comptes "
                "dans un même groupe pour lancer la fusion."
            ))

        # 1. Vérification des périodes verrouillées
        self._check_locked_periods(sources if sources else all_selected)

        # 2. Calcul de l'aperçu (pour le log et le contrôle de volume)
        lines = self.env['account.move.line'].search([('account_id', 'in', sources.ids)]) if sources else self.env['account.move.line']
        line_count = len(lines)
        balance_before = sum(lines.mapped('balance'))

        # 3. Mode simulation : on s'arrête ici
        if self.dry_run:
            self.env['account.merge.log'].create({
                'wizard_reference': str(self.id),
                'source_account_ids': [(6, 0, sources.ids)],
                'line_count': line_count,
                'balance_before_source': balance_before,
                'state': 'dry_run',
                'notes': "Simulation uniquement, aucune donnée modifiée.",
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Simulation terminée"),
                    'message': _(
                        "%(count)s pièces auraient été transférées. "
                        "Décochez 'Mode simulation' pour exécuter réellement."
                    ) % {'count': line_count},
                    'sticky': True,
                }
            }

        # 4. Anti-clic-accidentel sur les gros volumes
        if line_count > 100 and self.confirmation_text != 'CONFIRMER':
            raise UserError(_(
                "%(count)s pièces vont être transférées. Par sécurité, tapez "
                "CONFIRMER dans le champ prévu avant de relancer l'action."
            ) % {'count': line_count})

        # 5. Exécution réelle, protégée par un savepoint
        log_vals = {
            'wizard_reference': str(self.id),
            'source_account_ids': [(6, 0, sources.ids)],
            'line_count': line_count,
            'balance_before_source': balance_before,
        }
        try:
            with self.env.cr.savepoint():
                result = super().action_merge()
                log_vals.update({'state': 'done'})
                self.env['account.merge.log'].create(log_vals)
                _logger.info(
                    "Fusion comptes %s : %s pièces transférées.",
                    sources.mapped('code'), line_count,
                )
                return result
        except Exception as e:
            log_vals.update({'state': 'failed', 'error_message': str(e)})
            self.env['account.merge.log'].create(log_vals)
            _logger.exception("Échec fusion comptes %s", sources.mapped('code'))
            raise UserError(_(
                "La fusion a échoué et a été annulée (rollback automatique).\n"
                "Détail technique : %s"
            ) % str(e))
