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
        We NEVER create or load a real sale.order for the cart flow.
        Returning an empty recordset prevents:
          - _update_address crashes on login
          - 'Expected singleton: res.users()' in has_ecommerce_access
          - Any ghost SO being created in the database for anonymous cart visits
        """
        if request and getattr(request, 'website', None) and request.website.name == 'Emakhealthcare':
            return self.env['sale.order']
        return super().sale_get_order(force_create=force_create)
