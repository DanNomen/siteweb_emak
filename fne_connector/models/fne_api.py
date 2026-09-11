import json
import logging

import requests

import odoo
from odoo import SUPERUSER_ID, _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FneApiError(Exception):
    """Erreur renvoyée par la plateforme FNE ou par le transport HTTP."""

    def __init__(self, message, status_code=None, payload=None, is_network=False):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload
        # is_network=True => on ne sait pas si la FNE a traité la demande.
        # Ne JAMAIS rejouer automatiquement une certification dans ce cas.
        self.is_network = is_network


class FneApi(models.AbstractModel):
    """Couche transport isolée : aucune logique métier ici.

    Surchargez cette classe pour brancher un mock en tests automatisés.
    """

    _name = "fne.api"
    _description = "Client HTTP de la plateforme FNE"

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------
    @api.model
    def sign_invoice(self, company, payload):
        """Certification d'une facture de vente ou d'un bordereau d'achat.

        POST $url/external/invoices/sign
        """
        return self._request(company, "POST", "/external/invoices/sign", payload)

    @api.model
    def refund_invoice(self, company, fne_invoice_id, payload):
        """Certification d'une facture d'avoir.

        POST $url/external/invoices/{id}/refund
        """
        if not fne_invoice_id:
            raise UserError(
                _("Impossible d'émettre un avoir : la facture d'origine n'a pas "
                  "d'identifiant FNE. Elle doit avoir été certifiée au préalable.")
            )
        endpoint = "/external/invoices/%s/refund" % fne_invoice_id
        return self._request(company, "POST", endpoint, payload)

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    @api.model
    def _request(self, company, method, endpoint, payload):
        base_url = (company.fne_base_url or "").rstrip("/")
        api_key = company.fne_api_key
        if not base_url or not api_key:
            raise UserError(
                _("La configuration FNE est incomplète pour la société %s : "
                  "renseignez l'URL de la plateforme et la clé API dans "
                  "Comptabilité > Configuration > Paramètres.", company.display_name)
            )

        url = base_url + endpoint
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer %s" % api_key,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        timeout = company.fne_timeout or 30

        log_vals = {
            "company_id": company.id,
            "move_id": self.env.context.get("fne_move_id"),
            "endpoint": url,
            "request_body": json.dumps(payload, indent=2, ensure_ascii=False),
        }

        _logger.info("FNE >>> %s %s", method, url)
        try:
            response = requests.request(
                method, url, headers=headers, data=body, timeout=timeout
            )
        except requests.exceptions.RequestException as exc:
            log_vals.update(state="network_error", response_body=str(exc))
            self._log(log_vals)
            raise FneApiError(
                _("La plateforme FNE est injoignable : %s", exc), is_network=True
            ) from exc

        raw = response.text or ""
        log_vals.update(status_code=response.status_code, response_body=raw[:60000])
        _logger.info("FNE <<< %s", response.status_code)

        try:
            data = response.json()
        except ValueError:
            data = None

        if response.status_code in (200, 201):
            log_vals["state"] = "success"
            self._log(log_vals)
            if not isinstance(data, dict):
                raise FneApiError(
                    _("Réponse FNE illisible (HTTP %s).", response.status_code),
                    status_code=response.status_code,
                    payload=raw,
                )
            return data

        log_vals["state"] = "error"
        self._log(log_vals)
        raise FneApiError(
            self._format_error(response.status_code, data, raw),
            status_code=response.status_code,
            payload=data or raw,
        )

    @api.model
    def _format_error(self, status_code, data, raw):
        if isinstance(data, dict):
            message = data.get("message") or data.get("error") or raw
            errors = data.get("errors")
            if errors:
                message = "%s\n%s" % (message, json.dumps(errors, indent=2, ensure_ascii=False))
        else:
            message = raw or _("Erreur inconnue")

        hints = {
            400: _("Données invalides. Vérifiez le point de vente, l'établissement "
                   "et les codes de TVA (ils doivent correspondre exactement au "
                   "paramétrage de votre espace FNE)."),
            401: _("Clé API refusée. Vérifiez la clé dans l'onglet « Paramétrage » "
                   "de votre espace FNE et l'URL utilisée (test vs production)."),
            404: _("Endpoint introuvable. Vérifiez que l'URL de base se termine "
                   "bien par /ws pour l'environnement de test."),
        }
        hint = hints.get(status_code)
        label = _("FNE — HTTP %s : %s", status_code, message)
        return "%s\n\n%s" % (label, hint) if hint else label

    @api.model
    def _log(self, vals):
        """Journalise dans un curseur dédié.

        Un refus de la FNE remonte en UserError, ce qui annule la transaction
        courante. La trace de ce qui a été envoyé doit survivre à ce rollback,
        sinon le diagnostic devient impossible.
        """
        try:
            with odoo.registry(self.env.cr.dbname).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env["fne.request.log"].create(vals)
        except Exception:  # noqa: BLE001 - la journalisation ne doit jamais casser le flux
            _logger.exception("FNE : impossible d'enregistrer la trace de la requête")
