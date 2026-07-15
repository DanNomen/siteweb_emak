# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import Controller, request
from datetime import datetime
from ..models.claim_reclamation import REASON


class ClaimController(Controller):

    @http.route("/claim/create", auth="public", website=True, sitemap=True)
    def claim_reclamation(self, **kw):
        """ Page de création d'une réclamation """
        template = "website_emakmed.claim_reclamation_template"
        return request.render(template, {})

    @http.route("/get_invoice_lines", type="json", auth="user", website=True)
    def get_invoice_products(self, **kw):
        """ Récupère les lignes de la facture sélectionnée """
        invoice_number = kw.get("name")
        if not invoice_number:
            return {"error": "Numéro de facture manquant"}

        invoice = request.env["account.move"].sudo().search([
            ("name", "=", invoice_number),
            ("state", "=", "posted")
        ], limit=1)

        if not invoice:
            return {"error": "Aucune facture trouvée pour ce numéro"}

        lines = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id and getattr(l.product_id, 'detailed_type', l.product_id.type) == 'consu'
        )

        datas = [
            {
                "id": line.id,
                "name": line.name,
                "qty": line.quantity,
                "reasons": dict(REASON),
            }
            for line in lines
        ]
        return {"lines": datas}

    @http.route(
        "/submit/claim",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def submit_reclamation(self, **kwargs):
        """ Soumission d'une réclamation """
        user = request.env.user.sudo()
        invoice_obj = request.env["account.move"].sudo()
        invoice_name = kwargs.get("invoice_number")

        if not invoice_name:
            return request.redirect("/claim/create")

        invoice_id = invoice_obj.search([("name", "=", invoice_name), ("state", "=", "posted")], limit=1)
        if not invoice_id:
            return request.redirect("/claim/create")

        claim_line = []
        is_product_checked = False
        message = kwargs.get("message", "")

        for line in invoice_id.invoice_line_ids:
            selection = f"selection_{line.id}"
            if selection in kwargs and kwargs.get(selection) == "on":
                claim_line.append(
                    (
                        0,
                        0,
                        {
                            "product_id": line.product_id.id,
                            "reason": kwargs.get(f"reason_{line.id}"),
                            "quantity": int(kwargs.get(f"qty_{line.id}", 1)),
                        },
                    )
                )
                is_product_checked = True

        # Si aucun produit sélectionné, on renvoie sur la page
        if not is_product_checked:
            products = invoice_id.invoice_line_ids.mapped("product_id")
            context = {
                "products": products,
                "name": invoice_name,
                "button_text": "Valider la réclamation",
            }
            return request.render("website_emakmed.claim_reclamation_template", context)

        # Création de la réclamation
        claim_vals = {
            "name": invoice_name,
            "user_id": user.id,
            "state": "draft",
            "message": message,
            "line_ids": claim_line,
        }
        request.env["claim.reclamation"].sudo().create(claim_vals)
        return request.render("website_emakmed.reclamation_thankyou")

    @http.route("/claim/your_claims", auth="user", website=True, sitemap=True)
    def claim_lists(self, **kw):
        """ Liste des réclamations visibles pour l'utilisateur """
        user = request.env.user.sudo()

        # 1. Ses propres réclamations
        # 2. Réclamations des utilisateurs dont le partner_id est dans allowed_clients
        allowed_partners = user.allowed_clients
        allowed_user_ids = request.env['res.users'].sudo().search([
            ('partner_id', 'in', allowed_partners.ids)
        ]).ids

        domain = [
            "|",
            ("user_id", "=", user.id),
            ("user_id", "in", allowed_user_ids)
        ]

        claims = request.env["claim.reclamation"].sudo().search(domain, order="create_date desc")
        template = "website_emakmed.claim_reclamation_list_template"
        return request.render(template, {"claims": claims})

    @http.route(
        "/claim/your_claims/<int:claim_id>",
        auth="user",
        website=True,
        sitemap=True,
    )
    def claim_details(self, claim_id, **kw):
        """ Détail d'une réclamation visible par l'utilisateur """
        user = request.env.user.sudo()
        allowed_partners = user.allowed_clients
        allowed_user_ids = request.env['res.users'].sudo().search([
            ('partner_id', 'in', allowed_partners.ids)
        ]).ids

        claim = request.env["claim.reclamation"].sudo().search([
            ("id", "=", claim_id),
            "|",
            ("user_id", "=", user.id),
            ("user_id", "in", allowed_user_ids)
        ], limit=1)

        if not claim:
            return request.redirect("/claim/your_claims")

        vals = {"claim": claim}
        return request.render("website_emakmed.claim_detail_template", vals)
