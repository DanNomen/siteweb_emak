# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# A ADAPTER avant utilisation :
# - DOMAIN_LOCAL : domaine utilisé en local (voir fichier hosts) / en prod
# - COMPANY_NAME : nom exact de la société
# - CURRENCY_XMLID : devise de la société (ex. XOF pour le Franc CFA)
# --------------------------------------------------------------------------
COMPANY_NAME = "Emakhealthcare"
WEBSITE_NAME = "Emakhealthcare"
DOMAIN_LOCAL = "emakhealthcare.local:8018"  # en prod : "emakhealthcare.com"
CURRENCY_XMLID = "base.XOF"
LANG_XMLID = "base.lang_fr"


def post_init_hook(env):
    """Exécuté automatiquement à l'installation du module.
    Idempotent : peut être relancé (mise à jour du module) sans dupliquer
    la société, le site, ni la page d'accueil.
    """
    company = _get_or_create_company(env)
    website = _get_or_create_website(env, company)
    _set_custom_homepage(env, website)
    _setup_menus(env, website)
    _logger.info(
        "Emakhealthcare : société id=%s / site web id=%s (domaine: %s)",
        company.id, website.id, website.domain,
    )
    return website


def _get_or_create_company(env):
    Company = env["res.company"]
    company = Company.search([("name", "=", COMPANY_NAME)], limit=1)
    if company:
        _logger.info("Société '%s' déjà existante (id=%s) — réutilisée.", COMPANY_NAME, company.id)
        return company

    currency = env.ref(CURRENCY_XMLID, raise_if_not_found=False)
    vals = {"name": COMPANY_NAME}
    if currency:
        vals["currency_id"] = currency.id

    company = Company.create(vals)
    _logger.info("Société '%s' créée (id=%s).", COMPANY_NAME, company.id)
    return company


def _get_or_create_website(env, company):
    Website = env["website"]
    website = Website.search([("name", "=", WEBSITE_NAME)], limit=1)

    lang = env.ref(LANG_XMLID, raise_if_not_found=False)

    # Utilisateur public dédié au site. Sans ce champ correctement renseigné,
    # TOUT visiteur non connecté fait planter le site (Odoo essaie de
    # résoudre un utilisateur public inexistant -> erreur QWeb
    # "Expected singleton: res.users()" sur le header, sur toutes les
    # pages, y compris la page de login).
    public_user = env.ref("base.public_user", raise_if_not_found=False)

    if website:
        _logger.info("Site web '%s' déjà existant (id=%s) — mise à jour du domaine/société.", WEBSITE_NAME, website.id)
        vals = {
            "company_id": company.id,
            "domain": DOMAIN_LOCAL,
        }
        # On ne touche à user_id QUE s'il est manquant ou invalide : on ne
        # veut pas écraser un utilisateur public dédié déjà correctement
        # configuré (ex: si "Compte utilisateur spécifique" a été activé
        # manuellement dans Site Web > Configuration > Paramètres).
        if public_user and (not website.user_id or not website.user_id.exists() or not website.user_id.partner_id):
            vals["user_id"] = public_user.id
            _logger.warning(
                "Site '%s' : utilisateur public manquant/invalide -> réassigné à base.public_user (id=%s).",
                WEBSITE_NAME, public_user.id,
            )
        website.write(vals)
        return website

    vals = {
        "name": WEBSITE_NAME,
        "company_id": company.id,
        "domain": DOMAIN_LOCAL,
    }
    if lang:
        vals["default_lang_id"] = lang.id
    if public_user:
        vals["user_id"] = public_user.id

    website = Website.create(vals)
    _logger.info("Site web '%s' créé (id=%s).", WEBSITE_NAME, website.id)
    return website


def _set_custom_homepage(env, website):
    """Crée une page dédiée '/accueil-emakhealthcare' avec notre contenu,
    et fait pointer l'accueil du site vers cette page via homepage_url.

    On évite volontairement d'écraser l'arch_db d'une vue existante
    (page générée par l'assistant IA, thème, etc.) : cette vue peut être
    la cible d'un xpath depuis d'autres vues héritées (ex. '#wrap'),
    et l'écraser casse ces héritages. Une page neuve, autonome, est
    beaucoup plus sûre et n'interfère avec rien d'existant.
    """
    Page = env["website.page"]
    View = env["ir.ui.view"]
    arch = '<t t-call="website.layout"><t t-call="emakhealthcare_website.homepage_content"/></t>'

    view = View.search([
        ("key", "=", "emakhealthcare_website.custom_homepage_view"),
        ("website_id", "=", website.id),
    ], limit=1)

    if view:
        view.write({"arch_db": arch})
        _logger.info("Vue homepage dédiée mise à jour (id=%s).", view.id)
    else:
        view = View.create({
            "name": "Emakhealthcare - Accueil personnalisé",
            "key": "emakhealthcare_website.custom_homepage_view",
            "type": "qweb",
            "mode": "primary",
            "arch_db": arch,
            "website_id": website.id,
        })
        _logger.info("Vue homepage dédiée créée (id=%s).", view.id)

    page = Page.search([
        ("website_id", "=", website.id),
        ("url", "=", "/accueil-emakhealthcare"),
    ], limit=1)

    if not page:
        page = Page.create({
            "url": "/accueil-emakhealthcare",
            "website_id": website.id,
            "view_id": view.id,
            "is_published": True,
        })
        _logger.info("Page '/accueil-emakhealthcare' créée (id=%s).", page.id)
    elif page.view_id != view:
        page.write({"view_id": view.id})

    if website.homepage_url != "/accueil-emakhealthcare":
        website.write({"homepage_url": "/accueil-emakhealthcare"})
        _logger.info("homepage_url du site '%s' pointé vers '/accueil-emakhealthcare'.", website.name)


def _setup_menus(env, website):
    """Configure les menus exacts demandés pour le site Emakhealthcare."""
    Menu = env["website.menu"]
    root_menu = website.menu_id
    
    if not root_menu:
        _logger.warning("Aucun menu racine trouvé pour le site %s", website.name)
        return

    # Supprimer les menus existants (pour éviter les doublons avec les menus par défaut d'Odoo)
    existing_menus = Menu.search([("parent_id", "=", root_menu.id), ("website_id", "=", website.id)])
    existing_menus.unlink()

    # Créer les nouveaux menus
    menus_data = [
        {"name": "Accueil", "url": "/", "sequence": 10},
        {"name": "Produits", "url": "/shop", "sequence": 20},
        {"name": "Promotions", "url": "/shop", "sequence": 30},
        {"name": "Réclamation", "url": "/contactus", "sequence": 40},
        {"name": "Espace Clients", "url": "/my", "sequence": 50},
    ]

    for menu in menus_data:
        Menu.create({
            "name": menu["name"],
            "url": menu["url"],
            "sequence": menu["sequence"],
            "parent_id": root_menu.id,
            "website_id": website.id,
        })
    _logger.info("Menus personnalisés configurés pour le site '%s'.", website.name)

