# -*- coding: utf-8 -*-
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class ResUsersEmakhealthcare(models.Model):
    _inherit = 'res.users'

    def _is_public(self):
        """
        Fix critique Odoo 18 production :
        Dans certains contextes (t-nocache de website.layout, pages login…),
        self.env.user retourne un recordset vide res.users() au lieu de
        l'utilisateur public. La méthode native appelle ensure_one() qui
        provoque alors une erreur 500 'Expected singleton'.

        Ce patch intercepte ce cas et retourne True (= utilisateur public)
        ce qui est le comportement attendu pour un visiteur non connecté.
        """
        if not self:
            _logger.debug("_is_public called on empty user recordset, returning True (public)")
            return True
        return super()._is_public()
