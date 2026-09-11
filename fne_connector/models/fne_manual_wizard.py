from odoo import _, fields, models
from odoo.exceptions import UserError


class FneManualResultWizard(models.TransientModel):
    _name = "fne.manual.result.wizard"
    _description = "Saisie manuelle d'un résultat de certification FNE"

    move_id = fields.Many2one(
        "account.move", string="Facture", required=True, readonly=True,
    )
    fne_reference = fields.Char(string="N° légal FNE", required=True)
    fne_invoice_id = fields.Char(
        string="ID facture FNE",
        help="Identifiant technique de la facture dans l'espace FNE. Sans lui, "
             "aucun avoir ne pourra être rattaché à cette facture.",
    )
    fne_token = fields.Char(
        string="Jeton de vérification",
        help="URL de vérification, utilisée pour générer le QR code.",
    )

    def action_confirm(self):
        self.ensure_one()
        move = self.move_id
        if move.fne_reference:
            raise UserError(
                _("La facture %s porte déjà le numéro FNE %s.",
                  move.name, move.fne_reference)
            )
        move.sudo().write({
            "fne_state": "certified",
            "fne_reference": self.fne_reference,
            "fne_invoice_id": self.fne_invoice_id or False,
            "fne_token": self.fne_token or False,
            "fne_error_message": False,
            "fne_sent_date": fields.Datetime.now(),
        })
        move.message_post(
            body=_("Résultat FNE saisi manuellement par %s. Numéro légal : %s",
                   self.env.user.display_name, self.fne_reference)
        )
        return {"type": "ir.actions.act_window_close"}
