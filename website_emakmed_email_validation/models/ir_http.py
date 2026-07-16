# -*- coding: utf-8 -*-
import re
from odoo import models
from odoo.http import request
import logging
_logger = logging.getLogger(__name__)

# Regex to strip a leading locale prefix such as /fr_FR or /en_US from a path.
_LOCALE_RE = re.compile(r'^/[a-z]{2}[_-][A-Za-z]{2}(?=/|$)')

# These URL stems (without locale prefix) require the visitor to be logged in.
# The check strips any /xx_XX/ prefix so both /shop/checkout and
# /fr_FR/shop/checkout are caught correctly.
PROTECTED_PATHS = {
    '/shop/checkout',
    '/shop/confirm_order',
    '/shop/address',
    '/shop/address/submit',
    '/shop/payment',
    '/shop/payment/validate',
    '/confirm_order_web',
}


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls, endpoint):
        try:
            raw_path = request.httprequest.path or ''
        except Exception:
            raw_path = ''

        # Strip locale prefix, e.g. /fr_FR/shop/checkout → /shop/checkout
        path = _LOCALE_RE.sub('', raw_path)

        if path in PROTECTED_PATHS:
            try:
                user = request.env.user
                public_user = request.env.ref('base.public_user', raise_if_not_found=False)
                if public_user and user.id == public_user.id:
                    _logger.info(
                        'website_emakmed_email_validation: blocking anonymous access to %s → signup',
                        raw_path,
                    )
                    return request.redirect('/web/signup?redirect=/shop/cart')
            except Exception:
                pass  # If env isn't ready, let Odoo handle it normally

        return super()._dispatch(endpoint)

