from odoo import http
from odoo.http import request
from datetime import date, timedelta

class ClientPortalController(http.Controller):

    @http.route('/my-officine/compte-client', auth='user', website=True)
    def compte_client(self, **kw):
        user = request.env.user
        partner = user.partner_id

        # Récupération modèle facture
        Invoice = request.env['account.move']

        # Dates (mois courant & précédent)
        today = date.today()
        first_day_current_month = today.replace(day=1)
        last_day_previous_month = first_day_current_month - timedelta(days=1)
        first_day_previous_month = last_day_previous_month.replace(day=1)

        # === CA DU MOIS COURANT ===
        ca_mois = sum(Invoice.search([
            ('partner_id', '=', partner.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', first_day_current_month),
            ('invoice_date', '<=', today)
        ]).mapped('amount_total'))

        # === CA DU MOIS PRÉCÉDENT ===
        ca_mois_prec = sum(Invoice.search([
            ('partner_id', '=', partner.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', first_day_previous_month),
            ('invoice_date', '<=', last_day_previous_month)
        ]).mapped('amount_total'))

        # === EN COURS DE FACTURATION ===
        ca_en_cours_facturation = sum(Invoice.search([
            ('partner_id', '=', partner.id),
            ('move_type', '=', 'out_invoice'),
            ('state', 'in', ['draft', 'posted']),
        ]).mapped(lambda inv: inv.amount_total - inv.amount_residual))

        # === TOTAL RESTANT DÛ (EN COURS) ===
        total_en_cours = sum(Invoice.search([
            ('partner_id', '=', partner.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ]).mapped('amount_residual'))

        # === ÉVOLUTION % DU CA ===
        evolution = 0
        if ca_mois_prec > 0:
            evolution = ((ca_mois - ca_mois_prec) / ca_mois_prec) * 100

        # === TOTAL REMISE ===
        total_remise = 0
        invoices = Invoice.search([
            ('partner_id', '=', partner.id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
        ])

        for inv in invoices:
            for line in inv.invoice_line_ids:
                if line.discount:
                    remise_ligne = (line.price_unit * line.quantity) * (line.discount / 100)
                    total_remise += remise_ligne

        # === ESCOMPTE & RISTOURNE ===
        invoice_lines = request.env['account.move.line'].search([
            ('move_id.partner_id', '=', partner.id),
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('move_id.state', '=', 'posted')
        ])

        # Calcul: montant hors taxe × escompte % pour chaque ligne
        total_escompte = 0.0
        total_ristourne = 0.0
        for line in invoice_lines:
            if line.escompte > 0:
                price_subtotal = line.price_subtotal or 0.0
                total_escompte += price_subtotal * (line.escompte / 100.0)
            if line.ristourne > 0:
                price_subtotal = line.price_subtotal or 0.0
                total_ristourne += price_subtotal * (line.ristourne / 100.0)

        invoice_lines_with_discount = invoice_lines.filtered(
            lambda l: l.escompte > 0 or l.ristourne > 0 or l.discount > 0
        )

        # Devise
        currency = request.env.company.currency_id

        values = {
            'partner': partner,
            'currency': currency,

            # CA
            'ca_mois': ca_mois,
            'ca_mois_prec': ca_mois_prec,
            'evolution': evolution,
            'ca_en_cours_facturation': ca_en_cours_facturation,
            'total_en_cours': total_en_cours,

            # Reductions
            'total_remise': total_remise,
            'total_escompte': total_escompte,
            'total_ristourne': total_ristourne,
            'invoice_lines': invoice_lines_with_discount,

            # Liste factures
            'invoices': invoices,
        }

        return request.render('website_emakmed.client_portal_page', values)