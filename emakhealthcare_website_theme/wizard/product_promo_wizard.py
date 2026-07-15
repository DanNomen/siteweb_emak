# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ProductPromoWizard(models.TransientModel):
    _name = 'product.promo.wizard'
    _description = 'Assistant de Promotion Produit'

    promo_type = fields.Selection(
        selection=[
            ('pct',      'Remise en pourcentage (ex: -20%)'),
            ('bogo',     '1 acheté = 1 offert'),
            ('bundle',   'Pack / Bundle (achat groupé)'),
            ('qty',      'Remise sur quantité (ex: 3 pour 2)'),
            ('free_ship','Livraison gratuite'),
            ('other',    'Autre promotion'),
            ('none',     'Aucune (Retirer la promotion)'),
        ],
        string="Type de promotion",
        required=True,
        default='other'
    )
    
    promo_description = fields.Char(
        string="Description courte",
        help="Texte court affiché sur la vignette. Ex : '1 acheté = 1 offert'"
    )
    
    product_ids = fields.Many2many(
        'product.product',
        string="Variantes d'articles"
    )

    product_tmpl_ids = fields.Many2many(
        'product.template',
        string="Modèles d'articles"
    )
    
    @api.model
    def default_get(self, fields_list):
        res = super(ProductPromoWizard, self).default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model')
        
        if active_model == 'product.product':
            res['product_ids'] = [(6, 0, active_ids)]
        elif active_model == 'product.template':
            res['product_tmpl_ids'] = [(6, 0, active_ids)]
            
        return res

    def action_apply_promo(self):
        """Applique la promotion sur les templates de produits associés."""
        templates = self.env['product.template']
        
        # Récupérer les templates des variantes sélectionnées
        if self.product_ids:
            templates |= self.product_ids.mapped('product_tmpl_id')
            
        # Ajouter les templates sélectionnés directement
        if self.product_tmpl_ids:
            templates |= self.product_tmpl_ids
            
        if not templates:
            raise UserError(_("Aucun article sélectionné."))

        # Mettre à jour les modèles de produits
        val_to_write = {
            'promo_type': self.promo_type if self.promo_type != 'none' else False,
            'promo_description': self.promo_description if self.promo_type != 'none' else False,
        }
        
        templates.write(val_to_write)
        
        return {'type': 'ir.actions.act_window_close'}
