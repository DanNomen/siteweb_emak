# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    from odoo.addons.emakhealthcare_website.hooks import (
        _get_or_create_company,
        _get_or_create_website,
        _set_custom_homepage,
    )

    company = _get_or_create_company(env)
    website = _get_or_create_website(env, company)
    _set_custom_homepage(env, website)

    _logger.info(
        "[emakhealthcare_website] Migration %s : ciblage robuste de la homepage (site id=%s)",
        version, website.id,
    )
