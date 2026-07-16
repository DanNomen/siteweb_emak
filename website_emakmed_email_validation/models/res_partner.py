# -*- coding: utf-8 -*-
from odoo import models, api
import logging
_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        """Safety net: this database enforces a NOT NULL constraint on
        res_partner.company_id at the SQL level, but the Python field
        definition is not marked required=True. This means Odoo's ORM never
        checks/fills this value before issuing the INSERT, so any code path
        that creates a partner without an explicit company_id (e.g. the
        website signup flow, which is not company-aware) crashes with a raw
        PostgreSQL "NOT NULL constraint" error instead of a clean Odoo
        validation error.

        We fill it here, at the lowest common point (res.partner.create),
        so it's fixed regardless of which higher-level flow triggered the
        creation (auth_signup, contact form, import, etc.) instead of
        patching every individual caller.
        """
        default_company_id = self.env.company.id
        for vals in vals_list:
            if not vals.get('company_id'):
                vals['company_id'] = default_company_id
                _logger.info(
                    "res.partner.create: company_id was missing, defaulted to %s "
                    "(website_emakmed_email_validation safety net)", default_company_id
                )
        return super(ResPartner, self).create(vals_list)
