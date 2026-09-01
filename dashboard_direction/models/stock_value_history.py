# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StockValueHistory(models.Model):
    """Snapshot mensuel de la valeur du stock.
    Alimenté par un cron (voir ir.cron dans dashboard_security.xml ou data/cron.xml).
    Nécessaire car la valeur de stock est un instantané : on ne peut pas
    reconstituer 'la valeur au 31 mars' sans avoir stocké la donnée à ce moment.
    """
    _name = 'dashboard.stock.value.history'
    _description = "Historique mensuel de la valeur du stock"
    _order = 'snapshot_date desc'

    snapshot_date = fields.Date(required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    total_value = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)

    @api.model
    def _cron_snapshot_stock_value(self):
        """Calcule et enregistre la valeur totale du stock à la date du jour,
        par société. À planifier une fois par jour ou une fois par mois selon
        le besoin de granularité."""
        for company in self.env['res.company'].search([]):
            quants = self.env['stock.quant'].search([
                ('company_id', '=', company.id),
                ('location_id.usage', '=', 'internal'),
            ])
            total = sum(q.quantity * q.product_id.standard_price for q in quants)
            self.create({
                'snapshot_date': fields.Date.context_today(self),
                'company_id': company.id,
                'total_value': total,
                'currency_id': company.currency_id.id,
            })
