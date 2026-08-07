# -*- coding: utf-8 -*-
# from odoo import http


# class EmakPurchaseTtc(http.Controller):
#     @http.route('/emak_purchase_ttc/emak_purchase_ttc', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/emak_purchase_ttc/emak_purchase_ttc/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('emak_purchase_ttc.listing', {
#             'root': '/emak_purchase_ttc/emak_purchase_ttc',
#             'objects': http.request.env['emak_purchase_ttc.emak_purchase_ttc'].search([]),
#         })

#     @http.route('/emak_purchase_ttc/emak_purchase_ttc/objects/<model("emak_purchase_ttc.emak_purchase_ttc"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('emak_purchase_ttc.object', {
#             'object': obj
#         })

