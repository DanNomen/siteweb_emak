# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    # Désactivation de la vérification inter-société sur le partenaire de la facture.
    # Permet de facturer un client qui appartient formellement à une autre société
    partner_id = fields.Many2one(check_company=False)
    commercial_partner_id = fields.Many2one(check_company=False)
    partner_shipping_id = fields.Many2one(check_company=False)

    def _get_invoiced_lot_values(self):
        """
        Override pour contourner les restrictions multi-sociétés lors de
        l'accès aux produits dans l'impression de facture.
        
        Problème : Dani (Emakhealthcare) facture des produits appartenant à
        une autre société (SOF). Odoo bloque la lecture de product.product
        car les règles de société l'interdisent.
        
        Solution : Exécuter avec sudo() pour lever les restrictions d'accès
        produit lors du rendu du rapport de facture.
        """
        try:
            return super()._get_invoiced_lot_values()
        except Exception:
            # Fallback : exécuter en sudo pour contourner les restrictions inter-sociétés
            _logger.debug(
                "AccountMove[%s]: Accès cross-company détecté, utilisation du sudo pour _get_invoiced_lot_values",
                self.name
            )
            return self.sudo()._get_invoiced_lot_values_sudo()

    def _get_invoiced_lot_values_sudo(self):
        """Version sudo de _get_invoiced_lot_values pour l'accès cross-company."""
        # On recopie la logique Odoo core en mode sudo
        self.ensure_one()
        try:
            # Tenter d'appeler la méthode parente en mode sudo
            return super(AccountMove, self.sudo())._get_invoiced_lot_values()
        except Exception as e:
            _logger.warning(
                "AccountMove[%s]: Impossible de récupérer les lots même en sudo: %s",
                self.name, str(e)
            )
            return []


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def _get_product_catalog_record_lines(self, product_ids, **kwargs):
        """Override pour contourner les restrictions multi-sociétés."""
        try:
            return super()._get_product_catalog_record_lines(product_ids, **kwargs)
        except Exception:
            return self.sudo()._get_product_catalog_record_lines_sudo(product_ids, **kwargs)

    def _get_product_catalog_record_lines_sudo(self, product_ids, **kwargs):
        """Version sudo pour accès cross-company."""
        try:
            return super(AccountMoveLine, self.sudo())._get_product_catalog_record_lines(
                product_ids, **kwargs
            )
        except Exception as e:
            _logger.warning("AccountMoveLine: erreur sudo catalog: %s", str(e))
            return {}
