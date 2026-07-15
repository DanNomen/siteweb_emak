# -*- coding: utf-8 -*-
from odoo import api, fields, models


class LoyaltyRule(models.Model):
    _inherit = "loyalty.rule"

    def write(self, vals):
        """Surcharge pour mettre à jour automatiquement les produits quand ils sont ajoutés ou retirés d'une règle"""
        # Récupérer les produits avant la modification pour détecter ceux qui sont retirés
        products_before = set()
        for rule in self:
            products_before.update(rule.product_ids.ids)
        
        result = super(LoyaltyRule, self).write(vals)
        
        # Si des produits sont ajoutés ou modifiés dans la règle
        if 'product_ids' in vals:
            for rule in self:
                # Récupérer les produits après la modification
                products_after = set(rule.product_ids.ids)
                
                # Produits ajoutés
                products_added = products_after - products_before
                if products_added:
                    products = self.env['product.template'].browse(list(products_added))
                    products._update_promotion_dates_from_loyalty()
                
                # Produits retirés - nettoyer leurs dates
                products_removed = products_before - products_after
                if products_removed:
                    products = self.env['product.template'].browse(list(products_removed))
                    # Vérifier si ces produits ne sont plus dans aucune autre règle
                    for product in products:
                        other_rules = self.env['loyalty.rule'].search([
                            ('product_ids', 'in', [product.id]),
                            ('id', '!=', rule.id)
                        ])
                        if not other_rules:
                            # Le produit n'est plus dans aucune règle, nettoyer les dates
                            product.with_context(skip_loyalty_update=True).write({
                                'promotion_start_date': False,
                                'promotion_end_date': False,
                                'promotion_conditions': ''
                            })
                        else:
                            # Le produit est dans une autre règle, mettre à jour avec cette règle
                            product._update_promotion_dates_from_loyalty()
                
                # Produits toujours présents - mettre à jour au cas où les dates du programme ont changé
                products_still_present = products_after & products_before
                if products_still_present:
                    products = self.env['product.template'].browse(list(products_still_present))
                    products._update_promotion_dates_from_loyalty()
        
        return result

