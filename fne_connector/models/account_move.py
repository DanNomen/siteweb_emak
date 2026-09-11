import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .fne_api import FneApiError

_logger = logging.getLogger(__name__)

# Annexe 1 du document DGI
FNE_PAYMENT_METHODS = [
    ("cash", "Espèces"),
    ("card", "Carte bancaire"),
    ("check", "Chèque"),
    ("mobile-money", "Mobile money"),
    ("transfer", "Virement bancaire"),
    ("deferred", "À terme"),
]

FNE_FOREIGN_CURRENCIES = [
    "XOF", "USD", "EUR", "JPY", "CAD", "GBP", "AUD", "CNH", "CHF", "HKD", "NZD",
]


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    fne_item_id = fields.Char(
        string="ID article FNE",
        copy=False,
        readonly=True,
        help="Identifiant de la ligne attribué par la plateforme FNE. Indispensable "
             "pour émettre un avoir portant sur cette ligne.",
    )


class AccountMove(models.Model):
    _inherit = "account.move"

    fne_state = fields.Selection(
        [
            ("not_applicable", "Non applicable"),
            ("to_send", "À envoyer"),
            ("certified", "Certifiée"),
            ("error", "Erreur"),
            ("to_check", "À vérifier"),
        ],
        string="Statut FNE",
        default="not_applicable",
        copy=False,
        readonly=True,
        tracking=True,
        help="« À vérifier » signale une réponse jamais reçue : la facture a "
             "peut-être été certifiée côté DGI. Contrôlez dans votre espace FNE "
             "avant tout renvoi, sous peine de double certification.",
    )
    fne_reference = fields.Char(
        string="N° légal FNE", copy=False, readonly=True, index=True, tracking=True,
        help="Numéro officiel attribué par la plateforme FNE. C'est ce numéro qui "
             "fait foi fiscalement, et non la séquence Odoo.",
    )
    fne_invoice_id = fields.Char(string="ID facture FNE", copy=False, readonly=True)
    fne_token = fields.Char(
        string="Jeton de vérification", copy=False, readonly=True,
        help="URL à convertir en QR code et à apposer sur la facture.",
    )
    fne_qr_image = fields.Binary(
        string="QR code FNE", compute="_compute_fne_qr_image", store=False,
    )
    fne_balance_sticker = fields.Integer(string="Solde stickers", copy=False, readonly=True)
    fne_warning = fields.Char(string="Alerte FNE", copy=False, readonly=True)
    fne_error_message = fields.Text(string="Message d'erreur FNE", copy=False, readonly=True)
    fne_sent_date = fields.Datetime(string="Date de certification", copy=False, readonly=True)

    fne_invoice_type = fields.Selection(
        [("sale", "Vente"), ("purchase", "Bordereau d'achat de produits agricoles")],
        string="Type FNE",
        default="sale",
        copy=False,
    )
    fne_payment_method = fields.Selection(
        FNE_PAYMENT_METHODS,
        string="Mode de paiement FNE",
        compute="_compute_fne_payment_method",
        store=True,
        readonly=False,
        copy=False,
    )
    fne_point_of_sale = fields.Char(
        string="Point de vente FNE",
        compute="_compute_fne_place",
        store=True,
        readonly=False,
        copy=False,
    )
    fne_establishment = fields.Char(
        string="Établissement FNE",
        compute="_compute_fne_place",
        store=True,
        readonly=False,
        copy=False,
    )
    fne_is_rne = fields.Boolean(
        string="Adossée à un reçu (RNE)",
        copy=False,
        help="Cochez si la facture est rattachée à un reçu normalisé électronique.",
    )
    fne_rne = fields.Char(string="N° de reçu RNE", copy=False)
    fne_seller_name = fields.Char(string="Nom du vendeur", copy=False)

    # ------------------------------------------------------------------
    # Calculs
    # ------------------------------------------------------------------
    @api.depends("invoice_payment_term_id")
    def _compute_fne_payment_method(self):
        for move in self:
            if move.fne_payment_method:
                continue
            term = move.invoice_payment_term_id
            move.fne_payment_method = "deferred" if term else "cash"

    @api.depends("company_id")
    def _compute_fne_place(self):
        for move in self:
            move.fne_point_of_sale = move.fne_point_of_sale or move.company_id.fne_point_of_sale
            move.fne_establishment = move.fne_establishment or move.company_id.fne_establishment

    @api.depends("fne_token")
    def _compute_fne_qr_image(self):
        report = self.env["ir.actions.report"]
        for move in self:
            move.fne_qr_image = False
            if not move.fne_token:
                continue
            try:
                image = report.barcode("QR", move.fne_token, width=180, height=180)
                move.fne_qr_image = base64.b64encode(image)
            except Exception as e:  # noqa: BLE001
                _logger.warning("FNE : génération du QR code impossible pour %s : %s", move.name, e, exc_info=True)

    # ------------------------------------------------------------------
    # Éligibilité
    # ------------------------------------------------------------------
    def _fne_is_applicable(self):
        """Une pièce est concernée si c'est une facture ou un avoir client validé."""
        self.ensure_one()
        return bool(
            self.company_id.fne_enabled
            and self.move_type in ("out_invoice", "out_refund")
            and self.state == "posted"
        )

    # ------------------------------------------------------------------
    # Construction du payload
    # ------------------------------------------------------------------
    def _fne_get_lines(self):
        self.ensure_one()
        return self.invoice_line_ids.filtered(lambda l: l.display_type == "product")

    def _fne_line_taxes(self, line):
        """Éclate les taxes Odoo entre le champ `taxes` et le champ `customTaxes`."""
        vat_codes, custom_taxes = [], []
        for tax in line.tax_ids:
            if tax.price_include:
                raise UserError(
                    _("La taxe « %s » est incluse dans le prix. La plateforme FNE "
                      "attend des prix unitaires hors taxes : utilisez une taxe "
                      "hors prix.", tax.display_name)
                )
            if tax.fne_tax_kind == "custom":
                custom_taxes.append({"name": tax.fne_custom_name, "amount": tax.amount})
            elif tax.fne_tax_kind == "vat" and tax.fne_vat_code:
                vat_codes.append(tax.fne_vat_code)
            else:
                raise UserError(
                    _("La taxe « %s » n'est pas mappée vers la FNE. Renseignez sa "
                      "nature et son code dans Comptabilité > Configuration > Taxes.",
                      tax.display_name)
                )

        if not vat_codes:
            raise UserError(
                _("La ligne « %s » n'a aucune TVA mappée FNE. Chaque ligne doit "
                  "porter exactement un code TVA (TVA, TVAB, TVAC ou TVAD).",
                  line.name or line.product_id.display_name)
            )
        if len(vat_codes) > 1:
            raise UserError(
                _("La ligne « %s » porte plusieurs codes TVA FNE (%s). Un seul est "
                  "autorisé par ligne.",
                  line.name or line.product_id.display_name, ", ".join(vat_codes))
            )
        return vat_codes, custom_taxes

    def _fne_prepare_line(self, line):
        vat_codes, custom_taxes = self._fne_line_taxes(line)
        values = {
            "taxes": vat_codes,
            "description": (line.name or line.product_id.display_name or "")[:255],
            "quantity": line.quantity,
            "amount": line.price_unit,
            "discount": line.discount or 0,
        }
        if custom_taxes:
            values["customTaxes"] = custom_taxes
        if line.product_id and line.product_id.default_code:
            values["reference"] = line.product_id.default_code
        if line.product_uom_id:
            values["measurementUnit"] = line.product_uom_id.name
        return values

    def _fne_prepare_payload(self):
        """Payload de certification d'une facture de vente ou d'un bordereau."""
        self.ensure_one()
        partner = self.partner_id
        company = self.company_id
        template = partner._fne_get_template()

        lines = self._fne_get_lines()
        if not lines:
            raise UserError(_("La facture %s ne contient aucune ligne d'article.", self.name))

        payload = {
            "invoiceType": self.fne_invoice_type or "sale",
            "paymentMethod": self.fne_payment_method or "cash",
            "template": template,
            "isRne": bool(self.fne_is_rne),
            "clientCompanyName": (partner.name or "")[:255],
            "clientPhone": partner.phone or partner.mobile or "",
            "clientEmail": partner.email or "",
            "pointOfSale": self.fne_point_of_sale or "",
            "establishment": self.fne_establishment or "",
            "commercialMessage": company.fne_commercial_message or "",
            "footer": company.fne_footer or "",
            "foreignCurrency": "",
            "foreignCurrencyRate": 0,
            "items": [self._fne_prepare_line(line) for line in lines],
        }

        if self.fne_is_rne:
            if not self.fne_rne:
                raise UserError(_("Le numéro de reçu RNE est obligatoire lorsque la "
                                  "facture est adossée à un reçu."))
            payload["rne"] = self.fne_rne

        if template == "B2B":
            if not partner.fne_ncc:
                raise UserError(
                    _("Le NCC du client « %s » est obligatoire pour une facturation "
                      "B2B.", partner.display_name)
                )
            payload["clientNcc"] = partner.fne_ncc

        if self.fne_seller_name:
            payload["clientSellerName"] = self.fne_seller_name

        if template == "B2F":
            payload.update(self._fne_prepare_foreign_currency())

        return payload

    def _fne_prepare_foreign_currency(self):
        """foreignCurrency et foreignCurrencyRate sont obligatoires en B2F."""
        self.ensure_one()
        currency = self.currency_id
        code = currency.name
        if code not in FNE_FOREIGN_CURRENCIES:
            raise UserError(
                _("La devise %s n'est pas acceptée par la plateforme FNE. Devises "
                  "autorisées : %s.", code, ", ".join(FNE_FOREIGN_CURRENCIES))
            )
        company_currency = self.company_id.currency_id
        if currency == company_currency:
            return {"foreignCurrency": code, "foreignCurrencyRate": 1}
        rate = currency._convert(
            1.0, company_currency, self.company_id, self.invoice_date or fields.Date.today()
        )
        return {"foreignCurrency": code, "foreignCurrencyRate": rate}

    def _fne_prepare_refund_payload(self):
        """Payload d'avoir : identifiants FNE des lignes d'origine + quantités."""
        self.ensure_one()
        origin = self.reversed_entry_id
        if not origin:
            raise UserError(
                _("L'avoir %s n'est rattaché à aucune facture d'origine. Créez-le "
                  "depuis la facture concernée (bouton « Ajouter un avoir ») afin "
                  "que la FNE puisse rapprocher les lignes.", self.name)
            )
        if not origin.fne_invoice_id:
            raise UserError(
                _("La facture d'origine %s n'a pas été certifiée par la FNE : "
                  "aucun avoir ne peut lui être rattaché.", origin.name)
            )

        available = origin._fne_get_lines().filtered("fne_item_id")
        consumed = self.env["account.move.line"]
        items = []
        for line in self._fne_get_lines():
            match = (available - consumed).filtered(
                lambda l, ref=line: l.product_id == ref.product_id
                and l.currency_id.compare_amounts(l.price_unit, ref.price_unit) == 0
            )[:1]
            if not match:
                raise UserError(
                    _("Impossible de rapprocher la ligne « %s » d'une ligne de la "
                      "facture d'origine %s. La FNE exige l'identifiant exact de la "
                      "ligne certifiée : ne modifiez pas les articles ni les prix "
                      "dans un avoir.",
                      line.name or line.product_id.display_name, origin.name)
                )
            consumed |= match
            items.append({"id": match.fne_item_id, "quantity": line.quantity})

        return {"items": items}

    # ------------------------------------------------------------------
    # Certification
    # ------------------------------------------------------------------
    def action_fne_certify(self):
        """Action manuelle : lève l'erreur pour la rendre visible à l'utilisateur."""
        for move in self:
            if not move._fne_is_applicable():
                raise UserError(
                    _("La facture %s n'est pas éligible à la certification FNE "
                      "(vérifiez qu'elle est validée et que la FNE est activée).",
                      move.name)
                )
            move._fne_certify(raise_on_error=True)
        return True

    def action_fne_force_certified(self):
        """Sortie de secours pour un statut « À vérifier » confirmé côté DGI.

        À n'utiliser qu'après avoir constaté dans l'espace FNE que la facture a
        bien été certifiée, afin de resaisir manuellement le numéro légal.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Saisir le résultat FNE"),
            "res_model": "fne.manual.result.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def _fne_certify(self, raise_on_error=False):
        self.ensure_one()

        if self.fne_reference:
            _logger.info("FNE : %s déjà certifiée (%s), envoi ignoré",
                         self.name, self.fne_reference)
            return True

        if self.fne_state == "to_check":
            message = _(
                "La facture %s est en statut « À vérifier » : une précédente "
                "requête n'a jamais reçu de réponse. Vérifiez dans votre espace "
                "FNE si elle a été certifiée avant de la renvoyer, sinon vous "
                "risquez une double certification.", self.name
            )
            if raise_on_error:
                raise UserError(message)
            _logger.warning(message)
            return False

        fne_api = self.env["fne.api"].with_context(fne_move_id=self.id)
        try:
            if self.move_type == "out_refund":
                payload = self._fne_prepare_refund_payload()
                response = fne_api.refund_invoice(
                    self.company_id, self.reversed_entry_id.fne_invoice_id, payload
                )
            else:
                payload = self._fne_prepare_payload()
                response = fne_api.sign_invoice(self.company_id, payload)
        except FneApiError as exc:
            state = "to_check" if exc.is_network else "error"
            self.sudo().write({"fne_state": state, "fne_error_message": exc.message})
            self.message_post(body=_("Certification FNE échouée : %s", exc.message))
            if raise_on_error and not exc.is_network:
                raise UserError(exc.message) from exc
            return False
        except UserError as exc:
            self.sudo().write({"fne_state": "error", "fne_error_message": str(exc)})
            if raise_on_error:
                raise
            return False

        self._fne_apply_response(response)
        return True

    def _fne_apply_response(self, response):
        self.ensure_one()
        values = {
            "fne_state": "certified",
            "fne_reference": response.get("reference"),
            "fne_token": response.get("token"),
            "fne_balance_sticker": response.get("balance_sticker") or 0,
            "fne_warning": self._fne_format_warning(response.get("warning")),
            "fne_error_message": False,
            "fne_sent_date": fields.Datetime.now(),
        }
        invoice = response.get("invoice") or {}
        if invoice.get("id"):
            values["fne_invoice_id"] = invoice["id"]
        self.sudo().write(values)

        self._fne_store_item_ids(invoice.get("items") or [])

        body = _("Facture certifiée par la FNE. Numéro légal : %s",
                 values["fne_reference"] or _("non communiqué"))
        self.message_post(body=body)

        threshold = self.company_id.fne_sticker_threshold
        if threshold and 0 < values["fne_balance_sticker"] <= threshold:
            _logger.warning(
                "FNE : solde de stickers faible pour %s (%s restants)",
                self.company_id.display_name, values["fne_balance_sticker"],
            )

    def _fne_format_warning(self, warning):
        if warning in (False, None, "", "false"):
            return False
        return str(warning)

    def _fne_store_item_ids(self, remote_items):
        """Mémorise les identifiants de lignes FNE, requis pour les avoirs."""
        self.ensure_one()
        lines = self._fne_get_lines()
        remaining = lines
        for remote in remote_items:
            reference = remote.get("reference")
            description = remote.get("description")
            match = remaining.filtered(
                lambda l, r=reference, d=description: (
                    (r and l.product_id.default_code == r)
                    or (not r and d and (l.name or "").startswith(d[:40]))
                )
            )[:1]
            if not match:
                continue
            match.sudo().write({"fne_item_id": remote.get("id")})
            remaining -= match

        if remaining and len(remote_items) == len(lines):
            # Repli positionnel lorsque le rapprochement par référence a échoué.
            for line, remote in zip(lines, remote_items):
                if not line.fne_item_id:
                    line.sudo().write({"fne_item_id": remote.get("id")})

    # ------------------------------------------------------------------
    # Surcharges Odoo
    # ------------------------------------------------------------------
    def action_post(self):
        res = super().action_post()
        for move in self:
            if not move._fne_is_applicable():
                continue
            if not move.company_id.fne_certify_on_post:
                move.sudo().fne_state = "to_send"
                continue
            move._fne_certify(raise_on_error=move.company_id.fne_block_on_error)
        return res

    def button_draft(self):
        certified = self.filtered(lambda m: m.fne_reference)
        if certified:
            raise UserError(
                _("Les factures suivantes ont été certifiées par la FNE et ne "
                  "peuvent plus repasser en brouillon : %s.\n\nÉmettez un avoir.",
                  ", ".join(certified.mapped("name")))
            )
        return super().button_draft()

    def unlink(self):
        certified = self.filtered(lambda m: m.fne_reference)
        if certified:
            raise UserError(
                _("Suppression impossible : les factures %s sont certifiées par la FNE.",
                  ", ".join(certified.mapped("name")))
            )
        return super().unlink()

    # ------------------------------------------------------------------
    # Tâche planifiée
    # ------------------------------------------------------------------
    @api.model
    def _cron_fne_certify(self, limit=50):
        """Rejoue les factures en attente ou en erreur métier.

        Les factures en statut « À vérifier » sont volontairement exclues :
        seule une vérification humaine dans l'espace FNE peut les débloquer.
        """
        moves = self.search(
            [
                ("state", "=", "posted"),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("fne_state", "in", ("to_send", "error")),
                ("fne_reference", "=", False),
                ("company_id.fne_enabled", "=", True),
            ],
            limit=limit,
            order="invoice_date, id",
        )
        for move in moves:
            try:
                move._fne_certify(raise_on_error=False)
                self.env.cr.commit()
            except Exception:  # noqa: BLE001
                self.env.cr.rollback()
                _logger.exception("FNE : échec de la reprise pour %s", move.name)
        return True
