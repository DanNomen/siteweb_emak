# -*- coding: utf-8 -*-
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.http import request

class EmakmedUsernameAuthSignupHome(AuthSignupHome):

    def _prepare_signup_values(self, qcontext):
        """
        Surcharge pour inclure le champ 'username' dans les valeurs de création.
        Le module login_with_username gère la génération automatique d'email 
        si 'login' n'est pas fourni.
        """
        values = super(EmakmedUsernameAuthSignupHome, self)._prepare_signup_values(qcontext)
        
        # Si un nom d'utilisateur a été soumis dans le formulaire d'inscription
        if 'username' in qcontext:
            values['username'] = qcontext.get('username')
            
        return values
