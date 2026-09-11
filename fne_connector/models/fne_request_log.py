from odoo import fields, models


class FneRequestLog(models.Model):
    _name = "fne.request.log"
    _description = "Journal des échanges avec la plateforme FNE"
    _order = "create_date desc, id desc"
    _rec_name = "endpoint"

    company_id = fields.Many2one("res.company", string="Société", required=True, index=True)
    move_id = fields.Many2one("account.move", string="Facture", index=True, ondelete="set null")
    endpoint = fields.Char(string="Endpoint", required=True)
    status_code = fields.Integer(string="Code HTTP")
    state = fields.Selection(
        [
            ("success", "Succès"),
            ("error", "Erreur métier"),
            ("network_error", "Erreur réseau"),
        ],
        string="Statut",
        required=True,
        default="error",
    )
    request_body = fields.Text(string="Requête")
    response_body = fields.Text(string="Réponse")
