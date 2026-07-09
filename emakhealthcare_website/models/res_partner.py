# -*- coding: utf-8 -*-
import logging

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MIN_LOGIN_LENGTH = 4
MIN_PASSWORD_LENGTH = 6


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def emakhealthcare_create_portal_account(self, login, password):
        """Crée un compte portail (res.users) pour ce partenaire.

        Contrairement au mécanisme de "Sign Up" standard d'Odoo (module
        auth_signup), l'identifiant (login) n'est PAS obligatoirement une
        adresse e-mail : c'est un identifiant libre choisi par le client
        (ex: "adupont"), stocké tel quel sur res.users.login.

        Les informations du partenaire (nom, adresse, e-mail, téléphone)
        ne sont pas modifiées ici : elles ont déjà été enregistrées lors
        du passage de commande (formulaire d'adresse standard du site).

        :param str login: identifiant souhaité par le client.
        :param str password: mot de passe souhaité par le client.
        :return: le res.users créé (recordset sudo).
        :raises UserError: si les données sont invalides ou l'identifiant
            est déjà utilisé.
        """
        self.ensure_one()
        Users = self.env['res.users'].sudo()

        login = (login or '').strip()
        password = password or ''

        if len(login) < MIN_LOGIN_LENGTH:
            raise UserError(
                "L'identifiant doit contenir au moins %d caractères." % MIN_LOGIN_LENGTH
            )
        if len(password) < MIN_PASSWORD_LENGTH:
            raise UserError(
                "Le mot de passe doit contenir au moins %d caractères." % MIN_PASSWORD_LENGTH
            )

        # Un partenaire ne doit avoir qu'un seul compte utilisateur associé.
        existing_user = Users.search([('partner_id', '=', self.id)], limit=1)
        if existing_user:
            raise UserError(
                "Un compte existe déjà pour ces informations. Merci de vous connecter."
            )

        # L'identifiant doit être unique dans la base (comparaison insensible
        # à la casse, comme le fait Odoo pour le champ login).
        duplicate = Users.with_context(active_test=False).search(
            [('login', '=ilike', login)], limit=1
        )
        if duplicate:
            raise UserError(
                "Cet identifiant est déjà utilisé, merci d'en choisir un autre."
            )

        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)

        vals = {
            'name': self.name or login,
            'login': login,
            'password': password,
            'email': self.email,
            'partner_id': self.id,
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
        }

        try:
            # no_reset_password : on fournit déjà un mot de passe, on ne
            # veut pas qu'Odoo envoie un e-mail de "définissez votre mot
            # de passe" (comportement du signup standard).
            user = Users.with_context(no_reset_password=True).create(vals)
        except Exception as exc:  # noqa: BLE001 - on protège contre les
            # erreurs d'intégrité SQL (ex: identifiant pris entre-temps).
            _logger.warning("Emakhealthcare: échec création compte portail (login=%s): %s", login, exc)
            raise UserError(
                "Impossible de créer le compte avec cet identifiant. "
                "Merci d'en choisir un autre."
            )

        # On force l'appartenance au groupe "Portail" uniquement (pas
        # d'accès interne / backend), quel que soit le comportement par
        # défaut de la création.
        if portal_group:
            user.sudo().write({'groups_id': [(6, 0, [portal_group.id])]})

        _logger.info(
            "Emakhealthcare: compte portail créé pour le partenaire '%s' (id=%s, login=%s)",
            self.name, self.id, login,
        )
        return user
