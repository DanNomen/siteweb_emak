# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

EMAKHEALTHCARE_SITE = 'Emakhealthcare'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _is_anonymous_cart(self):
        """
        S'assure que le panier est considéré comme anonyme si le visiteur
        est public et qu'aucun email n'a encore été fourni.
        Ceci empêche le bypass de la page /shop/address si Odoo associe
        le panier à un utilisateur public générique qui a déjà une adresse par défaut.
        """
        res = super()._is_anonymous_cart()

        # Uniquement si on est dans un contexte de requête web
        if request and hasattr(request, 'website') and request.website:
            if request.website.name == EMAKHEALTHCARE_SITE:
                # Si l'utilisateur est public, mais que res=False (Odoo croit que l'adresse est remplie)
                if not res and request.env.user._is_public():
                    # Si le partenaire lié au panier n'a pas d'email, c'est qu'il n'a pas
                    # passé l'étape du formulaire /shop/address (où l'email est requis).
                    if not self.partner_id.email:
                        return True

        return res

    def _check_company(self, fnames=None):
        """
        Bypass la vérification multi-société sur les champs partner pour les commandes
        du site Emakhealthcare.

        Dans Odoo multi-société, les clients web sont des partenaires "globaux"
        (company_id=False) qui peuvent appartenir à plusieurs sociétés. La contrainte
        standard bloque leur association avec une commande d'une société spécifique.
        On contourne ce problème ici proprement pour ce site uniquement.
        """
        if self.env.context.get('skip_website_company_check'):
            return

        # Si la commande appartient au site Emakhealthcare, on ignore completement
        # _check_company car Odoo force la vérification de tous les champs 
        # si 'company_id' est modifié.
        orders_to_check = self.filtered(lambda o: not (o.website_id and o.website_id.name == EMAKHEALTHCARE_SITE))
        
        if orders_to_check:
            return super(SaleOrder, orders_to_check)._check_company(fnames=fnames)


class Website(models.Model):
    _inherit = 'website'

    def _prepare_sale_order_values(self, partner_sudo):
        """
        Override pour injecter le bon entrepôt pour le site Emakhealthcare.
        Sans cela, Odoo prend l'entrepôt par défaut qui appartient à une autre société
        et provoque une erreur de validation cross-company.
        """
        vals = super()._prepare_sale_order_values(partner_sudo)

        if self.name == EMAKHEALTHCARE_SITE:
            # Trouver l'entrepôt qui appartient à la société Emakhealthcare
            wh = self.env['stock.warehouse'].sudo().search(
                [('company_id', '=', self.company_id.id)], limit=1
            )
            if wh:
                vals['warehouse_id'] = wh.id
            else:
                _logger.warning(
                    'Emakhealthcare: Aucun entrepôt trouvé pour la société %s (id=%s). '
                    'Veuillez créer un entrepôt pour cette société.',
                    self.company_id.name, self.company_id.id
                )

        return vals

    def sale_get_order(self, force_create=False):
        """
        Override pour le site Emakhealthcare : injecte le contexte
        skip_website_company_check lors de la création de la commande.
        Cela permet aux clients (dont le partenaire appartient à une autre société)
        de passer des commandes sur ce site sans erreur multi-société.
        """
        if self.name == EMAKHEALTHCARE_SITE:
            return super(
                Website, self.with_context(skip_website_company_check=True)
            ).sale_get_order(force_create=force_create)
        return super().sale_get_order(force_create=force_create)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        """
        S'assure que les partenaires créés depuis le site Emakhealthcare
        sont des partenaires "globaux" (company_id=False), ce qui leur permet
        de passer des commandes sur n'importe quelle société.
        """
        if request and hasattr(request, 'website') and request.website:
            if request.website.name == EMAKHEALTHCARE_SITE:
                for vals in vals_list:
                    # Ne pas forcer si c'est un contact d'une société spécifique (type='contact' avec parent)
                    if not vals.get('parent_id') and 'company_id' not in vals:
                        vals['company_id'] = False

        return super().create(vals_list)
