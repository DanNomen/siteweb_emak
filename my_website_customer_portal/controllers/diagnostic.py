from odoo import http
from odoo.http import request

class DiagnosticController(http.Controller):
    @http.route('/test_uid', auth='public', website=True)
    def test_uid(self, **kw):
        user = request.env.user
        uid = request.env.uid
        is_public = user._is_public() if user else 'No user'
        return f"UID: {uid}, User: {user}, Is Public: {is_public}"
