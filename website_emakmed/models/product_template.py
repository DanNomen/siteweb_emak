# -*- coding: utf-8 -*-
from odoo import api, fields, models, api


class ProductTemplate(models.Model):
    _inherit = "product.template"

    sale_order_lines = fields.One2many("sale.order.line", "product_template_id")
    sale_order_count = fields.Float(
        string="Sale order count",
        compute="_compute_sale_order_count",
    )
    number_of_sales = fields.Float(string="Number of sales")
    promotion_start_date = fields.Date(string="Promotion start date")
    promotion_end_date = fields.Date(string="Promotion end date")
    promotion_conditions = fields.Text(string="Conditions du promotion")
    promotion_checking_available = fields.Boolean(
        string="Disponibilite de la promotion",
        compute="_compute_promotion_checking_available",
        store=True,
    )

    @api.depends("sale_order_lines.product_uom_qty")
    def _compute_sale_order_count(self):
        for product in self:
            order_lines = product.sale_order_lines.filtered(
                lambda l: l.order_id.state == "sale"
            )
            product.sale_order_count = len(order_lines)
            product.number_of_sales = sum(order_lines.mapped("product_uom_qty"))

    @api.onchange("public_categ_ids")
    def _onchange_public_categ_ids(self):
        categ_id = self.public_categ_ids[:1]._origin.id
        if categ_id == self.env.ref("website_emakmed.product_category_promotion").id:
            self.website_ribbon_id = self.env.ref(
                "website_emakmed.product_ribbon_promotion"
            ).id
        elif categ_id == self.env.ref("website_emakmed.product_category_new").id:
            self.website_ribbon_id = self.env.ref(
                "website_emakmed.product_ribbon_new"
            ).id
        elif categ_id == self.env.ref("website_emakmed.product_category_arrival").id:
            self.website_ribbon_id = self.env.ref(
                "website_emakmed.product_ribbon_arrival"
            ).id
        elif (
            categ_id == self.env.ref("website_emakmed.product_category_pre_arrival").id
        ):
            self.website_ribbon_id = self.env.ref(
                "website_emakmed.product_ribbon_pre_arrival"
            ).id

    def get_best_selling_products(self, limit=10):
        """Returns the best-selling products."""
        return self.search(
            [("number_of_sales", ">", 0)],
            order="number_of_sales desc",
            limit=limit,
        )

    @api.depends("promotion_start_date", "promotion_end_date")
    def _compute_promotion_checking_available(self):
        today = fields.Date.context_today(self)
        for product in self:
            if (
                product.promotion_start_date
                and product.promotion_end_date
                and product.promotion_start_date <= today <= product.promotion_end_date
            ):
                product.promotion_checking_available = True
            else:
                product.promotion_checking_available = False
                product.public_categ_ids = False
                product.website_ribbon_id = False
                product.promotion_conditions = ""

    def _update_promotion_ribbon_and_category(self):
        """Met à jour le ruban et la catégorie publique selon l'état de promotion_checking_available"""
        # Éviter la récursion
        if self.env.context.get('skip_ribbon_update'):
            return
        
        for product in self:
            if product.promotion_checking_available:
                # Si la promotion est disponible, mettre le ruban et la catégorie
                try:
                    promotion_categ = self.env.ref("website_emakmed.product_category_promotion")
                    promotion_ribbon = self.env.ref("website_emakmed.product_ribbon_promotion")
                    
                    # Préparer les valeurs à mettre à jour
                    update_vals = {}
                    
                    # Ajouter la catégorie promotion si elle n'est pas déjà présente
                    if promotion_categ.id not in product.public_categ_ids.ids:
                        current_categs = product.public_categ_ids.ids
                        current_categs.append(promotion_categ.id)
                        update_vals['public_categ_ids'] = [(6, 0, current_categs)]
                    
                    # Mettre le ruban promotion
                    if not product.website_ribbon_id or product.website_ribbon_id.id != promotion_ribbon.id:
                        update_vals['website_ribbon_id'] = promotion_ribbon.id
                    
                    # Mettre à jour si nécessaire
                    if update_vals:
                        product.with_context(skip_ribbon_update=True).write(update_vals)
                except Exception:
                    # Si les références n'existent pas, ignorer
                    pass
            else:
                # Si la promotion n'est plus disponible, nettoyer
                try:
                    promotion_categ = self.env.ref("website_emakmed.product_category_promotion")
                    promotion_ribbon = self.env.ref("website_emakmed.product_ribbon_promotion")
                    
                    # Préparer les valeurs à mettre à jour
                    update_vals = {}
                    
                    # Retirer la catégorie promotion si elle est présente
                    if promotion_categ.id in product.public_categ_ids.ids:
                        current_categs = product.public_categ_ids.ids
                        current_categs.remove(promotion_categ.id)
                        update_vals['public_categ_ids'] = [(6, 0, current_categs)]
                    
                    # Retirer le ruban si c'est le ruban promotion
                    if product.website_ribbon_id and product.website_ribbon_id.id == promotion_ribbon.id:
                        update_vals['website_ribbon_id'] = False
                    
                    # Mettre à jour si nécessaire
                    if update_vals:
                        product.with_context(skip_ribbon_update=True).write(update_vals)
                except Exception:
                    pass

    def _update_promotion_dates_from_loyalty(self):
        """Met à jour les dates de promotion avec les dates du programme de fidélité si le produit est dans les règles conditionnelles"""
        # Éviter la récursion en vérifiant le contexte
        if self.env.context.get('skip_loyalty_update'):
            return
        
        for product in self:
            # Chercher uniquement les règles de fidélité où le produit est explicitement sélectionné
            loyalty_rules = self.env['loyalty.rule'].search([
                ('product_ids', 'in', [product.id])
            ])
            
            if loyalty_rules:
                # Prendre la première règle trouvée et récupérer son programme
                for rule in loyalty_rules:
                    # Vérifier que le produit est vraiment dans cette règle
                    if product.id in rule.product_ids.ids:
                        # Accéder au programme de fidélité
                        if hasattr(rule, 'program_id') and rule.program_id:
                            program = rule.program_id
                            program_name = program.name if hasattr(program, 'name') else ''
                            # Récupérer les dates du programme
                            date_from = getattr(program, 'date_from', None) or getattr(program, 'date_begin', None)
                            date_to = getattr(program, 'date_to', None) or getattr(program, 'date_end', None)
                            
                            if date_from or date_to:
                                # Vérifier si les dates ou le nom du programme sont différents avant de mettre à jour
                                needs_update = (
                                    product.promotion_start_date != date_from or 
                                    product.promotion_end_date != date_to or
                                    product.promotion_conditions != program_name
                                )
                                
                                if needs_update:
                                    # Mettre à jour les dates de promotion et le nom du programme avec le flag pour éviter la récursion
                                    product.with_context(skip_loyalty_update=True).write({
                                        'promotion_start_date': date_from,
                                        'promotion_end_date': date_to,
                                        'promotion_conditions': program_name
                                    })
                                    print(f"Produit {product.name}: Dates mises à jour depuis le programme de fidélité")
                                    print(f"  Programme: {program_name}")
                                    print(f"  Date début: {date_from}")
                                    print(f"  Date fin: {date_to}")
                                break

    def write(self, vals):
        """Surcharge pour mettre à jour les dates de promotion depuis les règles de fidélité"""
        result = super(ProductTemplate, self).write(vals)
        
        # Mettre à jour les dates si le produit est dans les règles de fidélité (sauf si on est déjà dans une mise à jour)
        if not self.env.context.get('skip_loyalty_update'):
            self._update_promotion_dates_from_loyalty()
        
        # Mettre à jour le ruban et la catégorie selon promotion_checking_available
        # Vérifier si promotion_checking_available a changé ou si c'est une mise à jour de dates
        if 'promotion_checking_available' in vals or 'promotion_start_date' in vals or 'promotion_end_date' in vals:
            self._update_promotion_ribbon_and_category()
        
        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge pour mettre à jour les dates après création"""
        products = super(ProductTemplate, self).create(vals_list)
        # Mettre à jour les dates si les produits sont dans les règles de fidélité
        if not self.env.context.get('skip_loyalty_update'):
            products._update_promotion_dates_from_loyalty()
        # Mettre à jour le ruban et la catégorie
        products._update_promotion_ribbon_and_category()
        return products