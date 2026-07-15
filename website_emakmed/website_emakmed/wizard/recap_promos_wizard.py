# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import datetime, date


class RecapPromosWizard(models.TransientModel):
    _name = 'recap.promos.wizard'
    _description = 'Récapitulatif des Promotions Wizard'

    start_date = fields.Date(
        string='Date de début',
        required=True,
        default=lambda self: date.today().replace(day=1)
    )
    end_date = fields.Date(
        string='Date de fin',
        required=True,
        default=lambda self: date.today()
    )

    def action_print_report(self):
        """Génère le rapport PDF"""
        self.ensure_one()
        return {
            'type': 'ir.actions.report',
            'report_name': 'website_emakmed.recap_promos_report',
            'report_type': 'qweb-pdf',
            'report_file': 'website_emakmed.recap_promos_report',
            'context': {
                'start_date': self.start_date,
                'end_date': self.end_date,
            },
            'data': {
                'start_date': self.start_date,
                'end_date': self.end_date,
            }
        }

