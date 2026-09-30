# -*- coding: utf-8 -*-
from odoo import models, api, _
import logging
import json

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _is_emakmed_website(self):
        if not self.website_id:
            return False
        return self.website_id.name != 'Emakhealthcare'

    def _cart_update(self, product_id=None, line_id=None, add_qty=0, set_qty=0, **kwargs):
        # Assainir kwargs pour éviter TypeError si des attributs personnalisés arrivent sous forme de chaîne JSON
        for attr_key in ('product_custom_attribute_values', 'no_variant_attribute_values'):
            if attr_key in kwargs and isinstance(kwargs[attr_key], str):
                try:
                    kwargs[attr_key] = json.loads(kwargs[attr_key])
                except Exception:
                    kwargs[attr_key] = []

        if not self._is_emakmed_website():
            return super()._cart_update(
                product_id=product_id, line_id=line_id,
                add_qty=add_qty, set_qty=set_qty, **kwargs
            )

        if not product_id:
            return super()._cart_update(
                product_id=product_id, line_id=line_id,
                add_qty=add_qty, set_qty=set_qty, **kwargs
            )

        product = self.env['product.product'].sudo().browse(int(product_id))

        if not product.exists():
            return super()._cart_update(
                product_id=product_id, line_id=line_id,
                add_qty=add_qty, set_qty=set_qty, **kwargs
            )

        is_storable = (
            getattr(product, 'is_storable', False) or
            product.type in ('product',)
        )
        if not is_storable:
            return super()._cart_update(
                product_id=product_id, line_id=line_id,
                add_qty=add_qty, set_qty=set_qty, **kwargs
            )

        warehouse = self.sudo().website_id.warehouse_id or self.sudo().warehouse_id
        product_with_ctx = product.sudo().with_context(warehouse=warehouse.id) if warehouse else product.sudo()

        available_qty = product_with_ctx.virtual_available

        if line_id:
            line = self.env['sale.order.line'].browse(line_id)
            current_qty = line.product_uom_qty if line.exists() else 0.0
        else:
            existing_lines = self.order_line.filtered(
                lambda l: l.product_id.id == int(product_id) and not l.display_type
            )
            current_qty = sum(existing_lines.mapped('product_uom_qty')) if existing_lines else 0.0

        if set_qty is not None and str(set_qty).strip() != '':
            new_qty = float(set_qty)
        elif add_qty is not None:
            new_qty = current_qty + float(add_qty)
        else:
            new_qty = current_qty

        if available_qty <= 0:
            _logger.warning(
                "[EmakMed] Produit en rupture de stock: %s (stock=%s)",
                product.name, available_qty
            )
            result = super()._cart_update(
                product_id=product_id, line_id=line_id,
                add_qty=0, set_qty=0, **kwargs
            )
            result['warning'] = _(
                "🔴 RUPTURE DE STOCK : Le produit \"%s\" est actuellement en rupture de stock. "
                "Vous ne pouvez pas l'ajouter au panier."
            ) % product.name
            return result

        if new_qty > available_qty:
            capped_qty = int(available_qty)
            _logger.warning(
                "[EmakMed] Quantité demandée (%s) > stock disponible (%s) pour '%s'. Plafonnement à %s.",
                new_qty, available_qty, product.name, capped_qty
            )
            result = super()._cart_update(
                product_id=product_id, line_id=line_id,
                add_qty=None, set_qty=capped_qty, **kwargs
            )
            result['warning'] = _(
                "⚠️ La quantité disponible pour \"%s\" est limitée à %d unité(s). "
                "Votre panier a été ajusté automatiquement."
            ) % (product.name, capped_qty)
            return result

        return super()._cart_update(
            product_id=product_id, line_id=line_id,
            add_qty=add_qty, set_qty=set_qty, **kwargs
        )
