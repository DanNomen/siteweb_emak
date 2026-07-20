/** @odoo-module **/

/**
 * Emakhealthcare — synchronisation du badge panier (header) avec le corps de page.
 *
 * PROBLÈME : le badge du header (.my_cart_quantity / .my_cart_amount) est rendu
 * côté serveur depuis request.session. Il n'est rafraîchi que lors d'un rechargement
 * complet. Quand le client change la quantité (+/-), Odoo n'envoie qu'un remplacement
 * partiel du DOM (website_sale.cart_lines + website_sale.total) via JSON-RPC, sans
 * recharger le header.
 *
 * SOLUTION : triple stratégie d'interception pour couvrir TOUS les canaux réseau
 * utilisés par Odoo (fetch, XMLHttpRequest, ou les deux selon la version / le widget).
 *
 * 1) Patch window.fetch  → capture les appels via l'API Fetch moderne.
 * 2) Patch XMLHttpRequest → capture les appels via XHR (JSON-RPC d'Odoo core).
 * 3) MutationObserver     → fallback : si le DOM du bloc "total" est remplacé
 *    et qu'il contient des attributs data-cart-amount / data-cart-qty injectés
 *    par le template serveur, on les lit et on met à jour le badge.
 */
(function () {
    "use strict";

    /* -----------------------------------------------------------------------
     * Constantes
     * -------------------------------------------------------------------- */
    var CART_ENDPOINTS = ["/shop/cart/update_json", "/shop/cart/update"];

    /* -----------------------------------------------------------------------
     * Helpers
     * -------------------------------------------------------------------- */
    function isCartUpdateUrl(url) {
        if (!url) { return false; }
        var s = typeof url === "string" ? url : (url.url || "");
        return CART_ENDPOINTS.some(function (ep) {
            return s.indexOf(ep) !== -1;
        });
    }

    function formatAmount(amount) {
        var value = Number(amount);
        if (isNaN(value)) { return null; }
        try {
            return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(value) + " CFA";
        } catch (e) {
            return String(Math.round(value)) + " CFA";
        }
    }

    /**
     * Met à jour les éléments du header à partir d'un objet payload.
     * Accepte le payload directement OU enveloppé dans { result: ... } (JSON-RPC 2.0).
     */
    function updateHeaderBadge(data) {
        if (!data || typeof data !== "object") { return; }
        var payload = ("result" in data) ? data.result : data;
        if (!payload || typeof payload !== "object") { return; }

        var amount  = payload.amount;
        var cartQty = payload.cart_quantity;

        if (typeof amount !== "undefined" && amount !== null) {
            var formatted = formatAmount(amount);
            if (formatted !== null) {
                document.querySelectorAll(".my_cart_amount").forEach(function (el) {
                    el.textContent = formatted;
                });
                console.debug("[EmakHC] Badge montant mis à jour \u2192", formatted);
            }
        }

        if (typeof cartQty !== "undefined" && cartQty !== null) {
            document.querySelectorAll(".my_cart_quantity").forEach(function (el) {
                el.textContent = cartQty;
            });
            console.debug("[EmakHC] Badge quantit\u00e9 mis à jour \u2192", cartQty);
        }
    }

    /* -----------------------------------------------------------------------
     * Guard : n'initialiser qu'une seule fois même si le script est rechargé
     * -------------------------------------------------------------------- */
    if (window.__emakhcCartSyncActive) { return; }
    window.__emakhcCartSyncActive = true;

    /* -----------------------------------------------------------------------
     * 1) Patch window.fetch
     * -------------------------------------------------------------------- */
    var _origFetch = window.fetch;
    window.fetch = function () {
        var args = arguments;
        var url  = args[0];
        var p    = _origFetch.apply(this, args);
        if (!isCartUpdateUrl(url)) { return p; }
        return p.then(function (response) {
            response.clone().json().then(updateHeaderBadge).catch(function () {});
            return response;
        });
    };

    /* -----------------------------------------------------------------------
     * 2) Patch XMLHttpRequest  (JSON-RPC d'Odoo core passe souvent par XHR)
     * -------------------------------------------------------------------- */
    var _origXhrOpen = XMLHttpRequest.prototype.open;
    var _origXhrSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function (method, url) {
        this.__emakhc_url = url || "";
        return _origXhrOpen.apply(this, arguments);
    };

    XMLHttpRequest.prototype.send = function () {
        if (isCartUpdateUrl(this.__emakhc_url)) {
            var xhr = this;
            xhr.addEventListener("load", function () {
                try {
                    var data = JSON.parse(xhr.responseText);
                    updateHeaderBadge(data);
                } catch (e) { /* réponse non-JSON, ignorer */ }
            });
        }
        return _origXhrSend.apply(this, arguments);
    };

    /* -----------------------------------------------------------------------
     * 3) MutationObserver — fallback DOM
     *    Si le bloc total swappé dans le DOM porte des attributs
     *    data-cart-amount / data-cart-qty (injectés côté serveur), on les lit.
     * -------------------------------------------------------------------- */
    var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(function (node) {
                if (node.nodeType !== 1) { return; }
                var candidates = [node].concat(Array.from(node.querySelectorAll("[data-cart-amount]")));
                candidates.forEach(function (el) {
                    if (!el.getAttribute) { return; }
                    var amt = el.getAttribute("data-cart-amount");
                    var qty = el.getAttribute("data-cart-qty");
                    if (amt !== null) {
                        updateHeaderBadge({
                            amount: parseFloat(amt),
                            cart_quantity: qty !== null ? parseInt(qty, 10) : undefined
                        });
                    }
                });
            });
        });
    });

    function startObserver() {
        if (document.body) {
            observer.observe(document.body, { childList: true, subtree: true });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", startObserver);
    } else {
        startObserver();
    }

    /* -----------------------------------------------------------------------
     * 4) Couverture jQuery (certains widgets Odoo utilisent encore $.ajax)
     * -------------------------------------------------------------------- */
    function hookJQuery($) {
        $(document).ajaxSuccess(function (event, xhr, settings, data) {
            if (isCartUpdateUrl(settings && settings.url)) {
                updateHeaderBadge(data);
            }
        });
    }

    if (window.jQuery) {
        hookJQuery(window.jQuery);
    } else {
        document.addEventListener("DOMContentLoaded", function () {
            if (window.jQuery) { hookJQuery(window.jQuery); }
        });
    }

    console.debug("[EmakHC] sync_header_cart.js charg\u00e9 (fetch + XHR + MutationObserver + jQuery).");
})();
