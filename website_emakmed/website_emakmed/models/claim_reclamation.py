from odoo import models, fields, api

REASON = [
    ("1", "Produit facturé non livré"),
    ("2", "Produit périmé"),
    ("3", "Produit cassé"),
    ("4", "Péremption Proche"),
    ("5", "Produit Avarié"),
    ("6", "Quantité facturée erronée"),
    ("7", "Produit Trop Cher"),
    ("8", "Retour Bon Etat"),
    ("9", "Retour Bon Etat – Doublon Commande"),
    ("10", "Retour Bon Etat – Erreur Commande"),
    ("11", "Produit facturé différent de produit livré"),
    ("12", "Produit livré en excédent"),
    ("13", "Rappel de Lot"),
]


class Claim(models.Model):
    _name = "claim.reclamation"
    _description = "Réclamation"
    _order = "id desc"

    name = fields.Char(string="N° de Facture", required=True, copy=False)
    name_sequence = fields.Char(string="N° de Réclamation", readonly=True, copy=False)
    message = fields.Char(string="Message")
    user_id = fields.Many2one(
        "res.users", string="Utilisateur", default=lambda self: self.env.user
    )
    claim_date = fields.Datetime(
        string="Date de Réclamation", default=fields.Datetime.now
    )
    close_date = fields.Datetime(string="Date de Clôture")
    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("closed", "Fermé"),
        ],
        string="État",
        default="draft",
    )
    line_ids = fields.One2many("claim.reclamation.line", "claim_id", string="Lignes")
    all_reasons = fields.Char(compute="_compute_all_reasons")

    @api.depends(("line_ids"))
    def _compute_all_reasons(self):
        for record in self:
            reason_labels = []
            for line in record.line_ids.filtered(lambda l: l.reason):
                reason_labels += [dict(line._fields["reason"].selection).get(line.reason)]
            record.all_reasons = ", ".join(reason_labels) if reason_labels else ""

    def action_close(self):
        for rec in self:
            rec.state = "closed"
            rec.close_date = fields.Datetime.now()

    def action_draft(self):
        for rec in self:
            rec.state = "draft"
            rec.close_date = False

    @api.model_create_multi
    def create(self, vals_list):
        """Génère le numéro de séquence lors de la création uniquement"""
        for vals in vals_list:
            # Générer la séquence uniquement si elle n'existe pas déjà
            # La séquence est générée uniquement au moment de la création
            sequence = self.env['ir.sequence'].next_by_code('claim.reclamation')
            if sequence:
                vals['name_sequence'] = sequence
        return super().create(vals_list)


class ClaimLine(models.Model):
    _name = "claim.reclamation.line"
    _description = "Ligne de Réclamation"

    claim_id = fields.Many2one("claim.reclamation", string="Réclamation")
    product_id = fields.Many2one("product.product", string="Produit")
    reason = fields.Selection(REASON, string="Motif de réclamation")
    quantity = fields.Float(string="Quantité")
    reason_display = fields.Char(string="Motif", compute="_compute_reason_display", store=False)

    @api.depends('reason')
    def _compute_reason_display(self):
        """Calcule le libellé du motif à partir de la sélection"""
        reason_dict = dict(REASON)
        for line in self:
            if line.reason:
                line.reason_display = reason_dict.get(line.reason, line.reason)
            else:
                line.reason_display = ""
