# -*- coding: utf-8 -*-
from odoo import models, fields, api
import uuid
import logging
_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def signup(self, values, token=None):
        _logger.warning("===== RES.USERS SIGNUP OVERRIDE EXECUTED =====")
        _logger.warning(f"Values before: {values}")

        company_id = values.get('company_id')
        if not company_id:
            website_id = self.env.context.get('website_id')
            company = self.env['website'].browse(website_id).company_id if website_id else self.env.company
            if company:
                company_id = company.id

        self_ctx = self
        if company_id:
            values.setdefault('company_id', company_id)
            values.setdefault('company_ids', [(4, company_id)])
            # IMPORTANT: putting company_id in `values` is NOT enough here.
            # The res.partner row behind the new user is created deeper in
            # auth_signup's own logic (create() or copy(), depending on
            # version/flow), and that call does not necessarily forward our
            # `values` dict to the partner. Odoo's ORM, however, ALWAYS
            # checks context['default_<field>'] as a fallback default for
            # any field left unset on ANY create() triggered during this
            # call - including the res.partner insert. This is what actually
            # fixes the "NULL value in column company_id of relation
            # res_partner" error, regardless of the exact internal signup
            # implementation.
            self_ctx = self.with_context(default_company_id=company_id)

        login = super(ResUsers, self_ctx).signup(values, token)

        # Safety net: in case some signup path still slips through (e.g. an
        # edge case not covered by default_company_id), make sure the new
        # user's partner ends up with a company_id set.
        if company_id:
            user = self.sudo().search([('login', '=', login)], limit=1)
            if user and not user.partner_id.company_id:
                user.partner_id.sudo().write({'company_id': company_id})

        return login


    is_email_verified = fields.Boolean(
        string='Email Verified', 
        default=False, 
        help='Indicates if the user has verified their email address.'
    )
    email_verification_token = fields.Char(string='Email Verification Token', copy=False)

    def action_send_verification_email(self):
        """Generates a token and sends the verification email to the user."""
        for user in self:
            if user.is_email_verified:
                continue
            
            token = str(uuid.uuid4())
            user.sudo().write({'email_verification_token': token})
            
            template = self.env.ref('website_emakmed_email_validation.mail_template_email_verification', raise_if_not_found=False)
            if template:
                template.sudo().send_mail(user.id, force_send=True)
