# -*- coding: utf-8 -*-
"""
Controller pour le site Emakhealthcare.

Hérite du controller de website_emakmed et remplace la page d'accueil
uniquement lorsque le site actif est le site Emakhealthcare (website_id=2).
Pour tous les autres sites, le comportement original est conservé.
"""
import logging
import math

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.website_emakmed.controllers.controllers import Website as EmakmedWebsite

_logger = logging.getLogger(__name__)

EMAKHEALTHCARE_WEBSITE_NAME = "Emakhealthcare"


class EmakhealthcareWebsite(EmakmedWebsite):
    """Surcharge du controller website_emakmed pour le site Emakhealthcare."""

    @http.route('/', auth="public", website=True, sitemap=True)
    def index(self, **kw):
        """Affiche la page d'accueil spécifique à Emakhealthcare."""
        current_website = request.website
        if current_website and current_website.name == EMAKHEALTHCARE_WEBSITE_NAME:
            _logger.debug(
                "Emakhealthcare homepage served for website '%s' (id=%s)",
                current_website.name, current_website.id,
            )
            ProductTemplate = request.env['product.template'].sudo()

            # Catégories publiques (max 6)
            categories = request.env['product.public.category'].sudo().search(
                [('parent_id', '=', False)], limit=6
            )

            # Offres spéciales : produits avec prix barré
            offers = ProductTemplate.search([
                ('website_published', '=', True),
                ('compare_list_price', '>', 0),
            ], limit=4)

            # Si pas d'offres avec promo, prendre les 4 premiers produits publiés
            if not offers:
                offers = ProductTemplate.search([
                    ('website_published', '=', True),
                ], limit=4)

            # Si toujours pas de produits publiés, prendre les 4 premiers produits
            if not offers:
                offers = ProductTemplate.search([], limit=4)

            values = {
                'categories': categories,
                'offers': offers,
                'website': current_website,
            }
            return request.render("emakhealthcare_website.homepage_content", values)

        # Comportement original pour tous les autres sites (ex. APPROMED MALI)
        return super().index(**kw)

    @http.route('/produits', auth="public", website=True, sitemap=True)
    def produits(self, page=1, search='', category=None, sort_by='name', **kw):
        """Page de liste de tous les produits pour le site Emakhealthcare."""
        current_website = request.website
        if not (current_website and current_website.name == EMAKHEALTHCARE_WEBSITE_NAME):
            return request.not_found()

        ProductTemplate = request.env['product.template'].sudo()
        PPCategory = request.env['product.public.category'].sudo()

        # Filtres
        domain = [('website_published', '=', True)]
        if search:
            domain += [('name', 'ilike', search)]
        category_id = int(category) if category and str(category).isdigit() else None
        if category_id:
            cat = PPCategory.search([('id', '=', category_id)], limit=1)
            if cat:
                domain += [('public_categ_ids', 'child_of', cat.id)]

        # Tri
        order_map = {
            'name': 'name asc',
            'price_asc': 'list_price asc',
            'price_desc': 'list_price desc',
            'newest': 'id desc',
        }
        order = order_map.get(sort_by, 'name asc')

        # Pagination
        PRODUCTS_PER_PAGE = 12
        product_count = ProductTemplate.search_count(domain)
        pager_pages = math.ceil(product_count / PRODUCTS_PER_PAGE) or 1
        current_page = max(1, min(int(page), pager_pages))
        offset = (current_page - 1) * PRODUCTS_PER_PAGE

        products = ProductTemplate.search(domain, limit=PRODUCTS_PER_PAGE, offset=offset, order=order)
        categories = PPCategory.search([('parent_id', '=', False)])

        values = {
            'products': products,
            'categories': categories,
            'search': search,
            'category': category_id,
            'sort_by': sort_by,
            'page': current_page,
            'page_count': pager_pages,
            'product_count': product_count,
            'website': current_website,
        }
        return request.render("emakhealthcare_website.products_page", values)

    # ------------------------------------------------------------------
    # Espace client : création de compte optionnelle après une commande
    # ------------------------------------------------------------------
    #
    # Ce mécanisme ne touche à aucune route ni logique standard du
    # processus de commande d'Odoo (website_sale) : il ajoute uniquement
    # un lien "Créer mon compte" sur la page de confirmation de commande
    # (/shop/confirmation), sécurisé par le couple (order_id, access_token)
    # propre à la commande concernée. Le client garde donc la possibilité
    # de commander en tant qu'invité (sans compte) : la création de
    # compte reste 100% optionnelle.

    def _emakhealthcare_get_order_from_token(self, order_id, access_token):
        """Retrouve la commande à partir de son id + access_token.

        Renvoie un recordset vide si les paramètres sont invalides,
        manquants, ou ne correspondent à aucune commande existante.
        Ce contrôle empêche un visiteur de créer un compte en usurpant
        l'id d'une commande qui n'est pas la sienne.
        """
        SaleOrder = request.env['sale.order'].sudo()
        if not order_id or not access_token:
            return SaleOrder
        try:
            order_id = int(order_id)
        except (TypeError, ValueError):
            return SaleOrder
        order = SaleOrder.browse(order_id).exists()
        if not order or not order.access_token or order.access_token != access_token:
            return SaleOrder
        return order

    @http.route(
        ['/mon-espace/creer-compte'],
        type='http', methods=['GET', 'POST'], auth='public', website=True, sitemap=False,
    )
    def emakhealthcare_create_account(self, order_id=None, access_token=None, **kw):
        """Formulaire de création de l'espace client, proposé au client
        juste après la confirmation d'une commande passée en invité.

        Demande uniquement un identifiant (login libre, pas forcément un
        e-mail) et un mot de passe : les autres informations (nom,
        adresse de livraison, e-mail, téléphone) ont déjà été saisies
        lors du passage de commande et sont automatiquement conservées,
        car le compte est rattaché au même partenaire (res.partner) que
        la commande.
        """
        order = self._emakhealthcare_get_order_from_token(order_id, access_token)
        if not order:
            return request.not_found()

        error = None
        success = False

        # Si un compte existe déjà pour ce partenaire, ou si le visiteur
        # est déjà connecté, il n'y a rien à faire ici.
        already_has_account = bool(
            request.env['res.users'].sudo().search([('partner_id', '=', order.partner_id.id)], limit=1)
        )
        if already_has_account and request.httprequest.method == 'GET':
            return request.redirect('/my')

        if request.httprequest.method == 'POST' and not already_has_account:
            login = (kw.get('login') or '').strip()
            password = kw.get('password') or ''
            password2 = kw.get('password2') or ''

            if password != password2:
                error = "Les deux mots de passe ne correspondent pas."
            else:
                try:
                    order.partner_id.sudo().emakhealthcare_create_portal_account(login, password)
                    success = True
                except UserError as exc:
                    error = str(exc)

            if success:
                # cr.commit() obligatoire : authenticate() ouvre son propre
                # curseur et ne voit pas l'utilisateur créé si la transaction
                # courante n'est pas validée.
                request.env.cr.commit()
                login_ok = False
                try:
                    credential = {'login': login, 'password': password, 'type': 'password'}
                    uid = request.session.authenticate(request.db, credential)
                    login_ok = bool(uid)
                except Exception:  # noqa: BLE001
                    _logger.warning(
                        "Emakhealthcare: compte créé (login=%s) mais connexion automatique impossible.",
                        login,
                    )

                if login_ok:
                    # Redirection immédiate après authenticate() : évite de
                    # rendre un template QWeb dans le même contexte de requête
                    # après un changement de session (provoque "Expected
                    # singleton: res.users()" sur les blocs t-nocache du
                    # header website_sale). Pattern identique à auth_signup.
                    return request.redirect('/my', 303)

        values = {
            'order': order,
            'error': error,
            'success': success,
            'already_has_account': already_has_account,
        }
        return request.render('emakhealthcare_website.create_account_page', values)
