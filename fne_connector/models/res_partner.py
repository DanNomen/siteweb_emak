from odoo import fields, models

FNE_TEMPLATES = [
    ("B2B", "B2B — entreprise ou professionnel possédant un NCC"),
    ("B2C", "B2C — particulier"),
    ("B2G", "B2G — institution gouvernementale"),
    ("B2F", "B2F — client à l'international"),
]


class ResPartner(models.Model):
    _inherit = "res.partner"

    fne_ncc = fields.Char(
        string="NCC",
        help="Numéro de Compte Contribuable du client. Obligatoire pour une "
             "facturation B2B.",
    )
    fne_template = fields.Selection(
        FNE_TEMPLATES,
        string="Type de facturation FNE",
        help="Laisser vide pour une déduction automatique :\n"
             "• pays différent de la Côte d'Ivoire → B2F\n"
             "• NCC renseigné → B2B\n"
             "• sinon → B2C\n"
             "B2G doit toujours être choisi manuellement.",
    )

    def _fne_get_template(self):
        """Détermine le template FNE applicable à ce partenaire."""
        self.ensure_one()
        if self.fne_template:
            return self.fne_template
        if self.country_id and self.country_id.code != "CI":
            return "B2F"
        if self.fne_ncc:
            return "B2B"
        return "B2C"
