# -*- coding: utf-8 -*-
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class WebsiteEmakhealthcare(models.Model):
    _inherit = 'website'

    def _get_product_available_qty(self, product, **kwargs):
        """
        Override pour le site Emakhealthcare :
        Additionne le stock disponible de TOUS les entrepôts des sociétés
        qui ont autorisé leur stock sur le site Emakhealthcare.

        Pour les autres sites, comportement standard (entrepôt du site uniquement).
        """
        # Appliquer uniquement pour le site Emakhealthcare
        # On identifie le site Emakhealthcare par son nom
        if 'emakhealthcare' not in (self.name or '').lower():
            return super()._get_product_available_qty(product, **kwargs)

        # Récupérer tous les entrepôts de toutes les sociétés autorisées
        # (le flag authorize_emakhealthcare_stock = True)
        authorized_companies = self.env['res.company'].sudo().search([
            ('authorize_emakhealthcare_stock', '=', True),
        ])

        if not authorized_companies:
            # Fallback : comportement standard
            _logger.warning("Emakhealthcare: Aucune société autorisée - vérifiez la configuration.")
            return super()._get_product_available_qty(product, **kwargs)

        warehouses = self.env['stock.warehouse'].sudo().search([
            ('company_id', 'in', authorized_companies.ids),
        ])

        if not warehouses:
            _logger.warning("Emakhealthcare: Aucun entrepôt trouvé pour les sociétés autorisées.")
            return super()._get_product_available_qty(product, **kwargs)

        # Additionner le stock disponible (free_qty) dans chaque entrepôt autorisé
        total_qty = 0.0
        for warehouse in warehouses:
            qty = product.with_context(warehouse_id=warehouse.id).free_qty
            _logger.debug(
                "Emakhealthcare stock: '%s' in WH '%s' (%s) = %s",
                product.name, warehouse.name, warehouse.company_id.name, qty
            )
            if qty > 0:
                total_qty += qty

        _logger.debug(
            "Emakhealthcare TOTAL stock for '%s': %s (across %d warehouses)",
            product.name, total_qty, len(warehouses)
        )

        return total_qty
