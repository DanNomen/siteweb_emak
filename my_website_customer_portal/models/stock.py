# -*- coding: utf-8 -*-
from odoo import models

class StockMove(models.Model):
    _inherit = 'stock.move'

    def _check_company(self, fnames=None):
        """
        Bypass la vérification multi-société pour les mouvements de stock 
        de la société Emakhealthcare. Cela permet à Emakhealthcare de vendre 
        ou déplacer des produits appartenant à d'autres sociétés.
        """
        def _should_check(m):
            # Bypass si le mouvement est dans la société Emakhealthcare
            if m.company_id.name == 'Emakhealthcare':
                return False
            # Bypass si le produit appartient à Emakhealthcare
            if m.product_id.company_id and m.product_id.company_id.name == 'Emakhealthcare':
                return False
            # Bypass si la commande client vient du site Emakhealthcare
            if m.sale_line_id and m.sale_line_id.order_id.website_id.name == 'Emakhealthcare':
                return False
            # Bypass si le BL (picking) vient d'une commande Emakhealthcare
            if m.picking_id and m.picking_id.sale_id and m.picking_id.sale_id.website_id.name == 'Emakhealthcare':
                return False
            return True

        moves_to_check = self.filtered(_should_check)
        if moves_to_check:
            return super(StockMove, moves_to_check)._check_company(fnames=fnames)

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _check_company(self, fnames=None):
        def _should_check(ml):
            if ml.company_id.name == 'Emakhealthcare':
                return False
            if ml.product_id.company_id and ml.product_id.company_id.name == 'Emakhealthcare':
                return False
            if ml.move_id.picking_id and ml.move_id.picking_id.sale_id and ml.move_id.picking_id.sale_id.website_id.name == 'Emakhealthcare':
                return False
            return True

        lines_to_check = self.filtered(_should_check)
        if lines_to_check:
            return super(StockMoveLine, lines_to_check)._check_company(fnames=fnames)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _check_company(self, fnames=None):
        pickings_to_check = self.filtered(
            lambda p: p.company_id.name != 'Emakhealthcare' and 
                      (not p.sale_id or p.sale_id.website_id.name != 'Emakhealthcare')
        )
        if pickings_to_check:
            return super(StockPicking, pickings_to_check)._check_company(fnames=fnames)

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(self, product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values):
        move_values = super(StockRule, self)._get_stock_move_values(product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values)
        
        sale_line_id = values.get('sale_line_id')
        if sale_line_id:
            sale_line = self.env['sale.order.line'].browse(sale_line_id)
            if sale_line.order_id.website_id.name == 'Emakhealthcare':
                # Chercher l'entrepôt qui possède le stock pour ce produit
                warehouses = self.env['stock.warehouse'].sudo().search([])
                best_wh = None
                for wh in warehouses:
                    product_with_ctx = product_id.with_context(warehouse=wh.id)
                    if product_with_ctx.virtual_available >= product_qty:
                        best_wh = wh
                        break
                
                if best_wh:
                    # Remplacer le type d'opération et l'emplacement d'origine par celui de l'entrepôt trouvé
                    move_values['location_id'] = best_wh.lot_stock_id.id
                    move_values['picking_type_id'] = best_wh.out_type_id.id
                    move_values['warehouse_id'] = best_wh.id
                    # On assigne également la société de l'entrepôt pour éviter les erreurs de compagnie
                    move_values['company_id'] = best_wh.company_id.id
                    
        return move_values
