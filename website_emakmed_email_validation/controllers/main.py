# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome

class EmailValidationSignup(AuthSignupHome):

    def get_auth_signup_qcontext(self):
        """Override to keep phone and street in qcontext if validation fails"""
        qcontext = super(EmailValidationSignup, self).get_auth_signup_qcontext()
        if request.params.get('phone'):
            qcontext['phone'] = request.params.get('phone')
        if request.params.get('street'):
            qcontext['street'] = request.params.get('street')
        return qcontext

    def _prepare_signup_values(self, qcontext):
        """Override to pass phone and street to the user creation"""
        values = super(EmailValidationSignup, self)._prepare_signup_values(qcontext)
        if request.params.get('phone'):
            values['phone'] = request.params.get('phone')
        if request.params.get('street'):
            values['street'] = request.params.get('street')
        return values

    def do_signup(self, qcontext):
        """Override to send verification email upon signup"""
        super(EmailValidationSignup, self).do_signup(qcontext)
        
        user = request.env.user
        if user and user.id != request.env.ref('base.public_user').id:
            # Send verification email if not already verified
            if not user.is_email_verified:
                user.sudo().action_send_verification_email()



class EmailValidationController(http.Controller):

    @http.route('/my/verify_email', type='http', auth='public', website=True, sitemap=False)
    def verify_email(self, token, **kwargs):
        if not token:
            return request.redirect('/shop')
            
        user = request.env['res.users'].sudo().search([('email_verification_token', '=', token)], limit=1)
        if user:
            user.sudo().write({
                'is_email_verified': True,
                'email_verification_token': False
            })
            return request.render('website_emakmed_email_validation.email_verification_success_template')
        else:
            return request.render('website_emakmed_email_validation.email_verification_failed_template')
            
    @http.route('/my/resend_verification_email', type='http', auth='user', website=True, sitemap=False)
    def resend_verification_email(self, **kwargs):
        user = request.env.user
        if not user.is_email_verified:
            user.sudo().action_send_verification_email()
        return request.redirect('/email_verification_required')


class EmailVerificationRequiredController(http.Controller):

    @http.route(['/email_verification_required'], type='http', auth="user", website=True, sitemap=False)
    def email_verification_required(self, **post):
        # Kept reachable directly (e.g. from the verification email itself)
        # but no longer reached automatically from checkout.
        if request.env.user.is_email_verified:
            return request.redirect('/shop/checkout')
        return request.render('website_emakmed_email_validation.email_verification_required_template')



# NOTE: we intentionally do NOT subclass WebsiteSale to override checkout()/
# confirm_order() anymore. Those method names are internal to website_sale
# and change between Odoo versions (this crashed in production with
# "'super' object has no attribute 'checkout'" because this Odoo version
# renamed/restructured that method). The "redirect public/anonymous users
# to login" behaviour is instead enforced version-safely in
# models/ir_http.py, which hooks into request dispatching itself rather
# than any specific website_sale controller method.


# Import the WebsiteConfirmOrder from website_emakmed to inherit it
try:
    from odoo.addons.website_emakmed.controllers.website_sale_confirm import WebsiteConfirmOrder

    class EmailValidationWebsiteConfirmOrder(WebsiteConfirmOrder):
        @http.route(['/confirm_order_web'], type='http', auth="public", website=True, csrf=True)
        def confirm_order(self, **kw):
            # Public/anonymous-user redirection is handled by the ir.http
            # dispatch hook (models/ir_http.py); by the time we get here the
            # user is guaranteed to be logged in.
            return super(EmailValidationWebsiteConfirmOrder, self).confirm_order(**kw)
except ImportError:
    pass
