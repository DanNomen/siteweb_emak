from odoo import api, fields, models

from .res_company import FNE_TEST_URL


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    fne_enabled = fields.Boolean(related="company_id.fne_enabled", readonly=False)
    fne_environment = fields.Selection(related="company_id.fne_environment", readonly=False)
    fne_base_url = fields.Char(related="company_id.fne_base_url", readonly=False)
    fne_api_key = fields.Char(related="company_id.fne_api_key", readonly=False)
    fne_ncc = fields.Char(related="company_id.fne_ncc", readonly=False)
    fne_point_of_sale = fields.Char(related="company_id.fne_point_of_sale", readonly=False)
    fne_establishment = fields.Char(related="company_id.fne_establishment", readonly=False)
    fne_commercial_message = fields.Char(related="company_id.fne_commercial_message", readonly=False)
    fne_footer = fields.Char(related="company_id.fne_footer", readonly=False)
    fne_certify_on_post = fields.Boolean(related="company_id.fne_certify_on_post", readonly=False)
    fne_block_on_error = fields.Boolean(related="company_id.fne_block_on_error", readonly=False)
    fne_timeout = fields.Integer(related="company_id.fne_timeout", readonly=False)
    fne_sticker_threshold = fields.Integer(related="company_id.fne_sticker_threshold", readonly=False)

    @api.onchange("fne_environment")
    def _onchange_fne_environment(self):
        """Repositionne l'URL de test, mais ne devine jamais l'URL de production."""
        for record in self:
            if record.fne_environment == "test":
                record.fne_base_url = FNE_TEST_URL
