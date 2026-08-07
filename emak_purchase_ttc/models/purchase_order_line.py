from odoo import models, fields, api

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    price_unit_ttc = fields.Float(
        string='Prix Unitaire TTC',
        compute='_compute_price_unit_ttc',
        inverse='_inverse_price_unit_ttc',
        digits='Product Price',
        store=True,
        readonly=False
    )

    @api.depends('price_unit')
    def _compute_price_unit_ttc(self):
        for line in self:
            line.price_unit_ttc = line.price_unit * 1.2

    def _inverse_price_unit_ttc(self):
        for line in self:
            line.price_unit = line.price_unit_ttc / 1.2

    @api.onchange('price_unit', 'price_unit_ttc')
    def _onchange_set_tax_20(self):
        tax_20 = self.env.ref('emak_purchase_ttc.tax_purchase_20', raise_if_not_found=False)
        if tax_20:
            self.taxes_id = [(6, 0, tax_20.ids)]
