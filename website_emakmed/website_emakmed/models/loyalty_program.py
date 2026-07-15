# -*- coding: utf-8 -*-
from odoo import api, fields, models


class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"

    def write(self, vals):
        """Surcharge pour mettre à jour automatiquement les produits quand les dates du programme changent"""
        result = super(LoyaltyProgram, self).write(vals)
        
        # Si les dates du programme sont modifiées, mettre à jour tous les produits liés
        date_fields = ['date_from', 'date_begin', 'date_to', 'date_end', 'name']
        if any(field in vals for field in date_fields):
            # Pour chaque programme modifié
            for program in self:
                # Trouver toutes les règles liées à ce programme
                rules = self.env['loyalty.rule'].search([
                    ('program_id', '=', program.id)
                ])
                
                # Récupérer tous les produits de ces règles
                product_ids = set()
                for rule in rules:
                    product_ids.update(rule.product_ids.ids)
                
                if product_ids:
                    # Mettre à jour automatiquement tous les produits liés
                    products = self.env['product.template'].browse(list(product_ids))
                    products._update_promotion_dates_from_loyalty()
                    products._update_promotion_ribbon_and_category()
        
        return result

