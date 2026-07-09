# -*- coding: utf-8 -*-
from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = 'res.company'

    authorize_emakhealthcare_stock = fields.Boolean(
        string="Autoriser le stock Emakhealthcare",
        default=False,
        help="Si coché, les produits de cette société avec du stock disponible seront visibles "
             "et vendables sur le site Emakhealthcare. Les produits sans stock resteront bloqués."
    )

    def action_authorize_emakhealthcare_stock(self):
        """Autorise cette société à partager son stock sur le site Emakhealthcare.
        Les produits sans stock restent bloqués (comportement normal)."""
        for company in self:
            company.authorize_emakhealthcare_stock = True
            _logger.info(
                "Emakhealthcare: La société '%s' a autorisé son stock sur le site.",
                company.name
            )

    def action_unauthorize_emakhealthcare_stock(self):
        """Révoque l'autorisation - les produits de cette société ne seront plus visibles."""
        for company in self:
            company.authorize_emakhealthcare_stock = False
            _logger.info(
                "Emakhealthcare: La société '%s' a révoqué son autorisation.",
                company.name
            )
