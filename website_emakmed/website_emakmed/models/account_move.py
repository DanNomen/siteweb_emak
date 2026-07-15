# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    escompte = fields.Float("Escompte %", default=0)
    ristourne = fields.Float("Ristourne %", default=0)

    @api.depends('quantity', 'discount', 'price_unit', 'tax_ids', 'currency_id', 'escompte', 'ristourne')
    def _compute_totals(self):
        super()._compute_totals()
        """ Compute 'price_subtotal' / 'price_total' outside of `_sync_tax_lines` because those values must be visible for the
        user on the UI with draft moves and the dynamic lines are synchronized only when saving the record.
        """
        AccountTax = self.env['account.tax']
        for line in self:
            # TODO remove the need of cogs lines to have a price_subtotal/price_total
            if line.display_type not in ('product', 'cogs'):
                line.price_total = line.price_subtotal = False
                continue

            base_line = line.move_id._prepare_product_base_line_for_taxes_computation(line)
            AccountTax._add_tax_details_in_base_line(base_line, line.company_id)
            line.price_subtotal = base_line['tax_details']['raw_total_excluded_currency']
            line.price_total = base_line['tax_details']['raw_total_included_currency']
            
            escompte_amount = line.quantity * line.price_unit * (line.escompte / 100)
            ristourne_amount = line.quantity * line.price_unit * (line.ristourne / 100)
            remise = line.quantity * line.price_unit * (line.discount / 100)
            line.price_subtotal = line.price_subtotal - (escompte_amount + ristourne_amount ) + remise
            line.price_total = line.price_total - (escompte_amount + ristourne_amount ) + remise

class AccountMove(models.Model):
    _inherit = "account.move"

    total_escompte = fields.Float("Total Escompte", compute='_compute_total_escompte', store=False)
    total_ristourne = fields.Float("Total Ristourne", compute='_compute_total_ristourne', store=False)

    @api.depends('line_ids.price_subtotal', 'line_ids.escompte', 'line_ids.product_id')
    def _compute_total_escompte(self):
        for move in self:
            total = 0.0
            for line in move.line_ids.filtered(lambda l: l.product_id and l.product_id.type == 'consu' and l.escompte > 0):
                # Calcul: montant hors taxe × escompte %
                escompte_amount = (line.quantity * line.price_unit) * (line.escompte / 100.0)
                total += escompte_amount
            move.total_escompte = total
    
    @api.depends('line_ids.price_subtotal', 'line_ids.ristourne', 'line_ids.product_id')
    def _compute_total_ristourne(self):
        for move in self:
            total = 0.0
            for line in move.line_ids.filtered(lambda l: l.product_id and l.product_id.type == 'consu' and l.ristourne > 0):
                # Calcul: montant hors taxe × ristourne %
                ristourne_amount = (line.quantity * line.price_unit) * (line.ristourne / 100.0)
                total += ristourne_amount
            move.total_ristourne = total

