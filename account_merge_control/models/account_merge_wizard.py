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
    preview_target_summary = fields.Char(
        string="Résumé cible(s)",
        readonly=True,
        help="Affiche clairement quel compte va absorber quels comptes.",
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
    # CŒUR DE LA LOGIQUE : détermination EXPLICITE cible / sources
    # par groupe, basée sur le nouveau champ is_target coché par l'utilisateur.
    # -------------------------------------------------------------------
    def _get_groups_target_and_sources(self):
        """Retourne une liste de tuples (target_account, source_accounts, group_lines)
        pour chaque groupe sélectionné.

        Lève une erreur claire si un groupe n'a pas exactement UNE ligne
        cochée comme cible (is_target), ou si une des sources a des pièces
        hachées (ce qui casserait l'inaltérabilité en la déplaçant).
        """
        self.ensure_one()
        selected_lines = self.wizard_line_ids.filtered(
            lambda l: l.display_type == 'account' and l.is_selected
        )
        if not selected_lines:
            raise UserError(_("Cochez au moins 2 comptes dans un même groupe."))

        results = []
        for grouping_key, group_lines in selected_lines.grouped('grouping_key').items():
            if len(group_lines) < 2:
                continue  # un seul compte coché dans ce groupe : rien à fusionner

            targets = group_lines.filtered('is_target')
            if len(targets) == 0:
                raise UserError(_(
                    "Groupe '%(codes)s' : aucun compte cible sélectionné. "
                    "Cochez la case 'Compte cible' sur le compte qui doit "
                    "SURVIVRE (ex: 41110000) avant de continuer."
                ) % {'codes': ', '.join(group_lines.mapped('account_id.code'))})
            if len(targets) > 1:
                raise UserError(_(
                    "Groupe '%(codes)s' : plusieurs comptes cibles cochés. "
                    "Ne cochez 'Compte cible' que sur UN SEUL compte par groupe."
                ) % {'codes': ', '.join(group_lines.mapped('account_id.code'))})

            target_line = targets
            source_lines = group_lines - target_line

            # Sécurité inaltérabilité : si une SOURCE (qui va être vidée/déplacée)
            # a des pièces hachées, on bloque, car déplacer ses écritures casse
            # la chaîne de hash. Le compte hachage doit être la CIBLE, pas la source.
            hashed_sources = source_lines.filtered('account_has_hashed_entries')
            if hashed_sources and not self.ignore_lock_date_check:
                raise UserError(_(
                    "Groupe '%(codes)s' : le(s) compte(s) %(hashed)s a/ont des "
                    "pièces hachées (inaltérabilité) et est/sont configuré(s) "
                    "comme SOURCE (à vider). Ceci casserait la chaîne de hash. "
                    "Cochez plutôt ce compte comme 'Compte cible', ou cochez "
                    "'Forcer même si période verrouillée' en connaissance de cause."
                ) % {
                    'codes': ', '.join(group_lines.mapped('account_id.code')),
                    'hashed': ', '.join(hashed_sources.mapped('account_id.code')),
                })

            results.append((target_line.account_id, source_lines.account_id, group_lines))
        return results

    # -------------------------------------------------------------------
    # ACTION APERÇU (dry-run preview)
    # -------------------------------------------------------------------
    def action_preview(self):
        """Calcule l'impact de la fusion sans rien modifier, et affiche
        clairement QUI absorbe QUOI."""
        self.ensure_one()
        groups = self._get_groups_target_and_sources()

        total_count = 0
        total_balance = 0.0
        summary_parts = []
        for target, sources, _lines in groups:
            lines = self.env['account.move.line'].search([('account_id', 'in', sources.ids)])
            total_count += len(lines)
            total_balance += sum(lines.mapped('balance'))
            summary_parts.append(
                "%s <- %s (%s pièces)" % (
                    target.code, ', '.join(sources.mapped('code')), len(lines)
                )
            )

        self.preview_line_count = total_count
        self.preview_balance = total_balance
        self.preview_target_summary = ' | '.join(summary_parts)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Aperçu de la fusion"),
                'message': _(
                    "%(summary)s\n\n"
                    "Total : %(count)s pièces, solde %(balance)s %(currency)s"
                ) % {
                    'summary': self.preview_target_summary,
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
        if self.ignore_lock_date_check:
            return
        company = self.env.company
        # Odoo 18 a retiré 'period_lock_date' (remplacé par le système
        # "Hard Lock date" / "Lock Everything" / exceptions par journal).
        # On reste défensif pour ne pas planter selon la version exacte.
        lock_date = (
            getattr(company, 'fiscalyear_lock_date', False)
            or getattr(company, 'hard_lock_date', False)
            or getattr(company, 'period_lock_date', False)
        )
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
        self.ensure_one()
        groups = self._get_groups_target_and_sources()

        all_sources = self.env['account.account']
        for _target, sources, _lines in groups:
            all_sources |= sources
        self._check_locked_periods(all_sources)

        # Calcul global (pour contrôle anti-clic et log)
        lines = self.env['account.move.line'].search([('account_id', 'in', all_sources.ids)])
        line_count = len(lines)
        balance_before = sum(lines.mapped('balance'))

        # Mode simulation : on s'arrête ici, log par groupe
        if self.dry_run:
            for target, sources, _lines in groups:
                grp_lines = self.env['account.move.line'].search([('account_id', 'in', sources.ids)])
                self.env['account.merge.log'].create({
                    'wizard_reference': str(self.id),
                    'source_account_ids': [(6, 0, sources.ids)],
                    'destination_account_id': target.id,
                    'line_count': len(grp_lines),
                    'balance_before_source': sum(grp_lines.mapped('balance')),
                    'state': 'dry_run',
                    'notes': "Simulation uniquement, aucune donnée modifiée.",
                })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Simulation terminée"),
                    'message': _(
                        "%(count)s pièces seraient transférées au total. "
                        "Décochez 'Mode simulation' pour exécuter réellement."
                    ) % {'count': line_count},
                    'sticky': True,
                }
            }

        # Anti-clic-accidentel sur les gros volumes
        if line_count > 100 and self.confirmation_text != 'CONFIRMER':
            raise UserError(_(
                "%(count)s pièces vont être transférées. Par sécurité, tapez "
                "CONFIRMER dans le champ prévu avant de relancer l'action."
            ) % {'count': line_count})

        # Exécution réelle, protégée par un savepoint, groupe par groupe
        try:
            with self.env.cr.savepoint():
                for target, sources, group_lines in groups:
                    grp_move_lines = self.env['account.move.line'].search(
                        [('account_id', 'in', sources.ids)]
                    )
                    grp_count = len(grp_move_lines)
                    grp_balance = sum(grp_move_lines.mapped('balance'))

                    # IMPORTANT : on passe la cible EN PREMIER, suivie des sources,
                    # pour forcer explicitement quel compte survit (au lieu de
                    # dépendre de l'ordre de séquence ou du tri par hash).
                    self._action_merge(target + sources)

                    self.env['account.merge.log'].create({
                        'wizard_reference': str(self.id),
                        'source_account_ids': [(6, 0, sources.ids)],
                        'destination_account_id': target.id,
                        'line_count': grp_count,
                        'balance_before_source': grp_balance,
                        'state': 'done',
                    })
                    _logger.info(
                        "Fusion : %s -> %s (%s pièces)",
                        sources.mapped('code'), target.code, grp_count,
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
            self.env['account.merge.log'].create({
                'wizard_reference': str(self.id),
                'source_account_ids': [(6, 0, all_sources.ids)],
                'line_count': line_count,
                'balance_before_source': balance_before,
                'state': 'failed',
                'error_message': str(e),
            })
            _logger.exception("Échec fusion comptes %s", all_sources.mapped('code'))
            raise UserError(_(
                "La fusion a échoué et a été annulée (rollback automatique).\n"
                "Détail technique : %s"
            ) % str(e))


class AccountMergeWizardLine(models.TransientModel):
    """Ajoute le champ 'Compte cible' explicite + neutralise la contrainte
    native qui bloque la fusion de comptes d'une même société."""
    _inherit = 'account.merge.wizard.line'

    is_target = fields.Boolean(
        string="Compte cible",
        help="Cochez UNIQUEMENT sur le compte qui doit survivre après la "
             "fusion (ex: 41110000). Les autres comptes cochés du même "
             "groupe seront vidés et transférés dans celui-ci."
    )

    def write(self, vals):
        """Si on coche is_target=True sur une ligne, décoche automatiquement
        les autres lignes du même groupe (comportement 'radio button')."""
        res = super().write(vals)
        if vals.get('is_target'):
            for line in self:
                siblings = line.wizard_id.wizard_line_ids.filtered(
                    lambda l: l.grouping_key == line.grouping_key and l.id != line.id
                )
                if siblings:
                    siblings.write({'is_target': False})
        return res

    def _apply_different_companies_constraint(self):
        """On autorise explicitement la fusion intra-société (cas EMAK/APPROMED :
        comptes dupliqués au sein de la MÊME société)."""
        return
