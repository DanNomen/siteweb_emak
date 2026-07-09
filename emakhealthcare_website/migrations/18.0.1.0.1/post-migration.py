# -*- coding: utf-8 -*-
"""
Script de post-migration.
Contrairement à post_init_hook (qui ne tourne qu'à l'installation),
ce script s'exécute à chaque fois que le numéro de version du module
change ET que vous lancez une mise à jour (-u emakhealthcare_website).

C'est le mécanisme correct pour rejouer une logique d'initialisation
(ici : recréer/rafraîchir la page d'accueil spécifique au site)
après la toute première installation.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Import différé pour éviter tout souci de chargement de module
    from odoo.addons.emakhealthcare_website.hooks import (
        _get_or_create_company,
        _get_or_create_website,
        _set_custom_homepage,
    )

    company = _get_or_create_company(env)
    website = _get_or_create_website(env, company)
    _set_custom_homepage(env, website)

    _logger.info(
        "[emakhealthcare_website] Migration %s : page d'accueil rafraîchie pour le site id=%s",
        version, website.id,
    )
