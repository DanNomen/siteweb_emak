# -*- coding: utf-8 -*-
import logging
import json

from odoo import _, http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


def _is_emakmed_website():
    website = getattr(request, 'website', None)
    if not website:
        return False
    return website.name != 'Emakhealthcare'


def _sanitize_cart_kwargs(kw):
    """S'assure que les attributs d'options sont convertis depuis JSON si nécessaire."""
    for attr_key in ('product_custom_attribute_values', 'no_variant_attribute_values'):
        if attr_key in kw and isinstance(kw[attr_key], str):
            try:
                kw[attr_key] = json.loads(kw[attr_key])
            except Exception:
                kw[attr_key] = []
    return kw


class WebsiteSaleEmakmedHideStock(WebsiteSale):

    @http.route(['/shop/cart/update'], type='http', auth="public", methods=['GET', 'POST'],
                website=True, csrf=False)
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kw):
        if not _is_emakmed_website():
            return super().cart_update(product_id=product_id, add_qty=add_qty, set_qty=set_qty, **kw)

        kw = _sanitize_cart_kwargs(kw)
        order = request.website.sale_get_order(force_create=True)

        values = order._cart_update(
            product_id=int(product_id),
            add_qty=add_qty,
            set_qty=set_qty,
            **kw
        )

        warning = values.get('warning')
        if warning:
            request.session['emakmed_stock_warning'] = warning
        else:
            request.session.pop('emakmed_stock_warning', None)

        is_ajax = request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest' or kw.get('xhr')
        if is_ajax:
            res_data = {
                'cart_quantity': order.cart_quantity,
                'warning': warning or False,
                'notification_info': {'warning': warning} if warning else {}
            }
            return request.make_response(
                json.dumps(res_data),
                headers=[('Content-Type', 'application/json')]
            )

        return request.redirect('/shop/cart')

    @http.route(['/shop/cart/update_json'], type='json', auth="public", methods=['POST'],
                website=True, csrf=False)
    def cart_update_json(self, product_id, line_id=None, add_qty=None, set_qty=None,
                         display=True, **kw):
        result = super().cart_update_json(
            product_id=product_id, line_id=line_id,
            add_qty=add_qty, set_qty=set_qty,
            display=display, **kw
        )

        if _is_emakmed_website():
            warning = request.session.pop('emakmed_stock_warning', None)
            if not warning and result.get('notification_info', {}).get('warning'):
                warning = result['notification_info']['warning']
            if warning:
                _logger.info("EmakMed stock alert: %s", warning)
                if 'notification_info' not in result:
                    result['notification_info'] = {}
                result['notification_info']['warning'] = warning
                result['warning'] = warning

        return result

