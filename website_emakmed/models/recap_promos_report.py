# -*- coding: utf-8 -*-

from odoo import api, models
from datetime import datetime


class RecapPromosReport(models.AbstractModel):
    _name = 'report.website_emakmed.recap_promos_report'
    _description = 'Rapport Récapitulatif des Promotions'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Génère les valeurs du rapport"""
        start_date = data and data.get('start_date') or self.env.context.get('start_date')
        end_date = data and data.get('end_date') or self.env.context.get('end_date')
        
        if not start_date or not end_date:
            return {
                'docs': [],
                'start_date': start_date,
                'end_date': end_date,
            }
        
        # Chercher les lignes de facture qui correspondent aux critères
        # - Montant total = 0
        # - Type consu
        # - Facturées entre les dates
        # - Facturées et livrées
        
        # Chercher d'abord les factures dans la période
        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('state', '=', 'posted'),
        ], order='invoice_date, name')
        
        # Ensuite chercher les lignes de facture correspondantes
        invoice_lines = self.env['account.move.line'].search([
            ('move_id', 'in', invoices.ids),
            ('product_id.type', '=', 'consu'),
            ('price_subtotal', '=', 0),
        ])
        
        # Grouper par facture pour calculer les quantités facturées
        report_lines = []
        processed_invoices = {}
        
        for line in invoice_lines:
            invoice = line.move_id
            invoice_id = invoice.id
            
            # Si on n'a pas encore traité cette facture, initialiser
            if invoice_id not in processed_invoices:
                # Calculer la quantité facturée (produits avec montant > 0 de type consu dans la même facture)
                paid_lines = self.env['account.move.line'].search([
                    ('move_id', '=', invoice_id),
                    ('product_id.type', '=', 'consu'),
                    ('price_subtotal', '>', 0),
                ])
                qty_facturee = sum(paid_lines.mapped('quantity'))
                
                processed_invoices[invoice_id] = {
                    'invoice': invoice,
                    'qty_facturee': qty_facturee,
                    'free_lines': []
                }
            
            # Ajouter cette ligne gratuite
            processed_invoices[invoice_id]['free_lines'].append(line)
        
        # Construire les lignes du rapport
        for invoice_id, invoice_data in processed_invoices.items():
            invoice = invoice_data['invoice']
            qty_facturee = invoice_data['qty_facturee']
            
            # Récupérer la commande associée à cette facture
            sale_order = invoice.invoice_line_ids.mapped('sale_line_ids').mapped('order_id')
            if not sale_order:
                continue
            
            order = sale_order[0]
            
            # Vérifier que la commande est livrée (toutes les lignes de type consu sont livrées)
            is_delivered = all(
                line.qty_delivered >= line.product_uom_qty 
                for line in order.order_line 
                if line.product_id.type == 'consu'
            ) if order.order_line else False
            
            if not is_delivered:
                continue
            
            # Pour chaque ligne gratuite, créer une ligne de rapport
            for free_line in invoice_data['free_lines']:
                report_lines.append({
                    'n_facture': invoice.name,
                    'pharmacie': invoice.partner_id.name,
                    'designation': free_line.product_id.name,
                    'date_commande': order.date_order.date() if order.date_order else False,
                    'qty_facturee': qty_facturee,
                    'unite_gratuite': free_line.quantity,
                })
        
        return {
            'docs': report_lines,
            'start_date': start_date,
            'end_date': end_date,
            'generated_date': datetime.now().strftime('%d/%m/%Y à %H:%M'),
        }

