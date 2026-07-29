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
        help="Dangereux : à cocher uniquement en connaissance de cause.",
    )
    confirmation_text = fields.Char(
        string="Tapez CONFIRMER pour valider",
        help="Sécurité anti-clic-accidentel sur un volume important de pièces.",
    )

    # -------------------------------------------------------------------
    # HELPERS : récupère les comptes sélectionnés depuis les lignes
    # NOTE : on n'exclut PAS les lignes ayant un champ 'info' (message
    #        d'avertissement), car on autorise explicitement la fusion
    #        de comptes appartenant à la même société (cas EMAK/APPROMED).
    # -------------------------------------------------------------------
    def _get_source_accounts_for_preview(self):
        """Retourne les comptes sources (lignes 2..N de chaque groupe sélectionné).

        Le 1er compte de chaque groupe devient la destination dans la logique
        native ; les suivants sont transférés vers lui.
        On inclut toutes les lignes is_selected, qu'elles aient un 'info' ou non.
        """
        self.ensure_one()
        selected_lines = self.wizard_line_ids.filtered(
            lambda l: l.display_type == 'account' and l.is_selected
        )
        sources = self.env['account.account']
        for group_lines in selected_lines.grouped('grouping_key').values():
            sorted_lines = group_lines.sorted('sequence')
            if len(sorted_lines) >= 2:
                # Les sources sont les comptes après le 1er (destination)
                sources |= sorted_lines[1:].account_id
        return sources

    def _get_all_selected_accounts(self):
        """Retourne tous les comptes sélectionnés (toutes positions)."""
        self.ensure_one()
        return self.wizard_line_ids.filtered(
            lambda l: l.display_type == 'account' and l.is_selected
        ).account_id

    # -------------------------------------------------------------------
    # ACTION APERÇU (dry-run preview)
    # -------------------------------------------------------------------
    def action_preview(self):
        """Calcule l'impact de la fusion sans rien modifier."""
        self.ensure_one()
        sources = self._get_source_accounts_for_preview()
        if not sources:
            raise UserError(_(
                "Sélectionnez au moins 2 comptes dans un même groupe pour "
                "calculer l'aperçu."
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
                    "%(count)s pièces comptables seront transférées depuis "
                    "%(nb_src)s compte(s) source.\n"
                    "Solde total concerné : %(balance)s %(currency)s"
                ) % {
                    'count': self.preview_line_count,
                    'nb_src': len(sources),
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
                "existent sur le(s) compte(s) source. Fusion bloquée. "
                "Cochez 'Forcer même si période verrouillée' pour outrepasser."
            ) % {'lock': lock_date})

    # -------------------------------------------------------------------
    # SURCHARGE action_merge : contrôles + dry-run + savepoint + audit
    # -------------------------------------------------------------------
    def action_merge(self):
        """Point d'entrée surchargé : ajoute contrôles, dry-run, savepoint et audit."""
        self.ensure_one()

        sources = self._get_source_accounts_for_preview()
        all_selected = self._get_all_selected_accounts()

        if not all_selected:
            raise UserError(_(
                "Sélectionnez au moins 2 comptes dans un même groupe."
            ))

        # 1. Vérification périodes verrouillées
        if sources:
            self._check_locked_periods(sources)

        # 2. Calcul de l'aperçu (pour log et contrôle de volume)
        line_count = 0
        balance_before = 0.0
        if sources:
            lines = self.env['account.move.line'].search([('account_id', 'in', sources.ids)])
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
                        "%(count)s pièces auraient été transférées depuis "
                        "%(nb)s compte(s) source. "
                        "Décochez 'Mode simulation' pour exécuter réellement."
                    ) % {'count': line_count, 'nb': len(sources)},
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
                # On appelle _action_merge directement par groupe pour contourner
                # le filtre 'not l.info' du super() qui bloque la fusion
                # intra-société (cas EMAK/APPROMED : 401100/40110000 même société).
                merged_any = False
                for group_lines in self.wizard_line_ids.filtered(
                    lambda l: l.display_type == 'account' and l.is_selected
                ).grouped('grouping_key').values():
                    sorted_lines = group_lines.sorted('sequence')
                    if len(sorted_lines) >= 2:
                        self._action_merge(
                            sorted_lines.sorted('account_has_hashed_entries', reverse=True).account_id
                        )
                        merged_any = True

                if not merged_any:
                    raise UserError(_(
                        "Aucun groupe avec au moins 2 comptes sélectionnés. "
                        "Impossible de lancer la fusion."
                    ))

                log_vals.update({'state': 'done'})
                self.env['account.merge.log'].create(log_vals)
                _logger.info(
                    "Fusion comptes %s : %s pièces transférées.",
                    sources.mapped('code'), line_count,
                )
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'success',
                        'sticky': False,
                        'message': _("Comptes fusionnés avec succès !"),
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }
        except UserError:
            raise
        except Exception as e:
            log_vals.update({'state': 'failed', 'error_message': str(e)})
            self.env['account.merge.log'].create(log_vals)
            _logger.exception("Échec fusion comptes %s", sources.mapped('code'))
            raise UserError(_(
                "La fusion a échoué et a été annulée (rollback automatique).\n"
                "Détail technique : %s"
            ) % str(e))


class AccountMergeWizardLine(models.TransientModel):
    """Surcharge de la ligne du wizard pour autoriser la fusion intra-société.

    La contrainte native '_apply_different_companies_constraint' bloque
    la fusion de deux comptes appartenant à la même société (elle pose un
    message d'erreur dans le champ 'info'). Pour le cas EMAK/APPROMED
    (401100 → 40110000, même société), on neutralise cette contrainte.
    """
    _inherit = 'account.merge.wizard.line'

    def _apply_different_companies_constraint(self):
        """On autorise explicitement la fusion intra-société.

        La fusion de comptes appartenant à la même société est techniquement
        supportée par _action_merge (il remplace simplement les FK). La
        contrainte native est une mesure de prudence qui ne correspond pas
        au besoin EMAK/APPROMED.
        """
        # No-op : on n'empêche pas la fusion intra-société.
        return
