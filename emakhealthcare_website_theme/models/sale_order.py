# -*- coding: utf-8 -*-
"""
Override sale.order pour le site Emakhealthcare.

Objectif : Quand une commande web Emakhealthcare est confirmée, les lignes
de bon de livraison doivent pointer vers l'entrepôt où le stock est réellement
disponible (parmi les sociétés autorisées), pas seulement l'entrepôt EC.

Approche :
- On surcharge _action_confirm / action_confirm
- Après la création des mouvements de stock, on réaffecte les emplacements
  d'origine en cherchant l'entrepôt qui a le stock disponible.
"""
import logging

from odoo import models, api

_logger = logging.getLogger(__name__)

EMAKHEALTHCARE_WEBSITE_NAME = "Emakhealthcare"


class SaleOrderEmakhealthcare(models.Model):
    _inherit = 'sale.order'

    def _get_emakhc_authorized_warehouses(self):
        """Retourne tous les entrepôts des sociétés autorisées sur le site Emakhealthcare."""
        authorized_companies = self.env['res.company'].sudo().search([
            ('authorize_emakhealthcare_stock', '=', True),
        ])
        if not authorized_companies:
            return self.env['stock.warehouse'].browse()
        return self.env['stock.warehouse'].sudo().search([
            ('company_id', 'in', authorized_companies.ids),
        ])

    def _is_emakhealthcare_order(self):
        """Vérifie si la commande provient du site Emakhealthcare."""
        website = self.website_id
        return website and EMAKHEALTHCARE_WEBSITE_NAME.lower() in (website.name or '').lower()

    def action_confirm(self):
        """Override pour forcer le bon entrepôt après confirmation."""
        res = super().action_confirm()
        for order in self:
            if not order._is_emakhealthcare_order():
                continue
            order._emakhc_assign_stock_locations()
        return res

    def _emakhc_assign_stock_locations(self):
        """
        Pour chaque mouvement de stock de la commande, cherche l'entrepôt
        qui a le stock disponible parmi les sociétés autorisées et réaffecte
        l'emplacement d'origine en conséquence.
        """
        self.ensure_one()
        warehouses = self._get_emakhc_authorized_warehouses()
        if not warehouses:
            _logger.warning(
                "Emakhealthcare: Aucun entrepôt autorisé trouvé pour la commande %s",
                self.name
            )
            return

        # Récupérer les pickings (bons de livraison) créés pour cette commande
        pickings = self.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        if not pickings:
            return

        for picking in pickings:
            for move in picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
                product = move.product_id
                if not product:
                    continue

                needed_qty = move.product_uom_qty

                # Chercher l'entrepôt avec le stock disponible (priorité : EC d'abord)
                best_warehouse = None
                best_qty = 0.0
                ec_warehouse = warehouses.filtered(
                    lambda w: 'emakhealthcare' in (w.company_id.name or '').lower()
                )[:1]

                # Vérifier d'abord l'entrepôt Emakhealthcare
                if ec_warehouse:
                    ec_qty = product.with_context(warehouse_id=ec_warehouse.id).free_qty
                    if ec_qty >= needed_qty:
                        best_warehouse = ec_warehouse
                        best_qty = ec_qty

                # Si pas assez dans EC, chercher dans les autres entrepôts
                if not best_warehouse:
                    for wh in warehouses:
                        qty = product.with_context(warehouse_id=wh.id).free_qty
                        if qty >= needed_qty and qty > best_qty:
                            best_warehouse = wh
                            best_qty = qty

                # Si toujours pas trouvé, prendre l'entrepôt avec le plus de stock
                if not best_warehouse:
                    for wh in warehouses:
                        qty = product.with_context(warehouse_id=wh.id).free_qty
                        if qty > best_qty:
                            best_warehouse = wh
                            best_qty = qty

                if not best_warehouse:
                    _logger.warning(
                        "Emakhealthcare: Aucun stock trouvé pour le produit '%s' dans les entrepôts autorisés. "
                        "Le mouvement %s garde l'emplacement par défaut.",
                        product.name, move.name
                    )
                    continue

                # Si l'entrepôt optimal est différent de l'emplacement actuel, on réaffecte
                current_src = move.location_id
                target_location = best_warehouse.lot_stock_id

                if current_src.id != target_location.id:
                    _logger.info(
                        "Emakhealthcare [%s]: Produit '%s' | Stock dispo: %.0f | "
                        "Src: %s → %s (%s)",
                        self.name, product.name, best_qty,
                        current_src.complete_name,
                        target_location.complete_name,
                        best_warehouse.company_id.name
                    )
                    try:
                        move.with_context(no_recompute=True).write({
                            'location_id': target_location.id,
                        })
                        # Mettre à jour le picking si tous les mouvements sont du même entrepôt
                        picking.location_id = target_location.id
                    except Exception as e:
                        _logger.error(
                            "Emakhealthcare: Impossible de réaffecter l'emplacement pour '%s': %s",
                            product.name, str(e)
                        )
                else:
                    _logger.debug(
                        "Emakhealthcare [%s]: Produit '%s' → Emplacement inchangé %s",
                        self.name, product.name, current_src.complete_name
                    )
