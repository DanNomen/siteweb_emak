# -*- coding: utf-8 -*-
import logging

from odoo import models, api
from odoo.http import request

_logger = logging.getLogger(__name__)


class Website(models.Model):
    _inherit = 'website'

    def sale_get_order(self, force_create=False):
        """
        On Emakhealthcare, cart items live entirely in request.session['deferred_cart'].

        During normal page rendering (force_create=False), we return an empty recordset
        to prevent Odoo from loading/creating a real sale.order, which would trigger
        _update_address() and crash with 'Expected singleton: res.users()'.

        When force_create=True (called by shop_checkout to persist the session cart
        into a real DB order before payment), we delegate to the standard implementation
        so the checkout flow can proceed normally.
        """
        if (not force_create
                and request
                and getattr(request, 'website', None)
                and request.website.name == 'Emakhealthcare'
                and request.session.get('deferred_cart')):
            return self.env['sale.order']
        return super().sale_get_order(force_create=force_create)
