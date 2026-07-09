# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Corrige automatiquement, lors de la mise à jour du module, le site
    Emakhealthcare déjà existant en base qui aurait été créé (par une
    version précédente du module) sans utilisateur public (user_id).

    Sans ce champ, tout visiteur non connecté fait planter le site
    (erreur QWeb "Expected singleton: res.users()" sur le header, sur
    toutes les pages, y compris la page de login).

    Ce script réutilise _get_or_create_website(), qui contient désormais
    la logique de correction : elle ne fait qu'ASSIGNER l'utilisateur
    public standard (base.public_user) si le champ est manquant ou
    invalide ; elle ne touche à rien d'autre sur un site déjà configuré.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    from odoo.addons.emakhealthcare_website.hooks import (
        _get_or_create_company,
        _get_or_create_website,
    )

    company = _get_or_create_company(env)
    website = _get_or_create_website(env, company)

    _logger.info(
        "[emakhealthcare_website] Migration %s : vérification/correction "
        "de l'utilisateur public du site '%s' (id=%s, user_id=%s)",
        version, website.name, website.id, website.user_id.id if website.user_id else False,
    )
