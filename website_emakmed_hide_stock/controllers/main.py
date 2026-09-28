# -*- coding: utf-8 -*-
import logging

from odoo import _, http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


def _is_emakmed_website():
    website = getattr(request, 'website', None)
    if not website:
        return False
    return website.name != 'Emakhealthcare'


class WebsiteSaleEmakmedHideStock(WebsiteSale):

    @http.route(['/shop/cart/update'], type='http', auth="public", methods=['GET', 'POST'],
                website=True, csrf=False)
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kw):
        if not _is_emakmed_website():
            return super().cart_update(product_id=product_id, add_qty=add_qty, set_qty=set_qty, **kw)

        order = request.website.sale_get_order(force_create=True)

        values = order._cart_update(
            product_id=int(product_id),
            add_qty=add_qty,
            set_qty=set_qty,
            **kw
        )

        if values.get('warning'):
            request.session['emakmed_stock_warning'] = values['warning']
        else:
            request.session.pop('emakmed_stock_warning', None)

        return request.redirect('/shop/cart')

    @http.route(['/shop/cart/update_json'], type='json', auth="public", methods=['POST'],
                website=True, csrf=False)
    def cart_update_json(self, product_id, line_id=None, add_qty=None, set_qty=None,
                         display=True, **kw):
        if not _is_emakmed_website():
            return super().cart_update_json(
                product_id=product_id, line_id=line_id,
                add_qty=add_qty, set_qty=set_qty,
                display=display, **kw
            )

        order = request.website.sale_get_order(force_create=True)
        if not order:
            return {}

        values = order._cart_update(
            product_id=int(product_id),
            line_id=line_id,
            add_qty=add_qty,
            set_qty=set_qty,
            **kw
        )

        order = request.website.sale_get_order()
        result = {
            'cart_quantity': order.cart_quantity if order else 0,
            'warning': values.get('warning', ''),
        }

        if values.get('warning'):
            _logger.info("EmakMed stock alert: %s", values['warning'])

        return result
