from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Annexe 1 du document DGI : codes de TVA acceptés par la plateforme.
FNE_VAT_CODES = [
    ("TVA", "TVA — taux normal 18 %"),
    ("TVAB", "TVAB — taux réduit 9 %"),
    ("TVAC", "TVAC — exonération conventionnelle 0 %"),
    ("TVAD", "TVAD — exonération légale 0 % (TEE et RME)"),
]


class AccountTax(models.Model):
    _inherit = "account.tax"

    fne_tax_kind = fields.Selection(
        [("vat", "TVA (champ taxes)"), ("custom", "Autre taxe (champ customTaxes)")],
        string="Nature FNE",
        help="Détermine dans quel champ du payload FNE la taxe est transmise.\n"
             "« TVA » alimente le tableau taxes de la ligne.\n"
             "« Autre taxe » alimente customTaxes (AIRSI, GRA, DTD...).",
    )
    fne_vat_code = fields.Selection(
        FNE_VAT_CODES,
        string="Code TVA FNE",
        help="Code attendu par la plateforme FNE pour cette TVA.",
    )
    fne_custom_name = fields.Char(
        string="Nom de la taxe FNE",
        help="Libellé exact attendu par la FNE pour une taxe autre que la TVA "
             "(ex. AIRSI, GRA, DTD).",
    )

    @api.constrains("fne_tax_kind", "fne_vat_code", "fne_custom_name")
    def _check_fne_mapping(self):
        for tax in self:
            if tax.fne_tax_kind == "vat" and not tax.fne_vat_code:
                raise ValidationError(
                    _("Taxe « %s » : un code TVA FNE est requis.", tax.display_name)
                )
            if tax.fne_tax_kind == "custom" and not tax.fne_custom_name:
                raise ValidationError(
                    _("Taxe « %s » : le nom de la taxe FNE est requis.", tax.display_name)
                )
