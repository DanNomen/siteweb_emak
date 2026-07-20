/** @odoo-module **/

/**
 * Emakhealthcare — session-based (deferred) cart.
 *
 * The header badge (".my_cart_quantity" / ".my_cart_amount") is rendered
 * server-side from request.session, and is only refreshed when the browser
 * does a full page load. When the customer changes the quantity in the cart
 * page (+/- buttons on /shop/cart) or clicks "Add to cart" elsewhere, the
 * update happens via an AJAX call to /shop/cart/update or
 * /shop/cart/update_json and the page is NOT reloaded — only the cart lines
 * / total blocks are swapped in the DOM. The header badge was therefore left
 * showing a stale amount/quantity from whenever the page was last fully
 * loaded.
 *
 * A previous fix injected a <script> tag directly inside the swapped
 * website_sale.cart_lines template to patch the DOM after each AJAX call,
 * but that was fragile (script tags inserted via innerHTML/OWL rendering are
 * not guaranteed to execute) and was later removed while fixing an unrelated
 * RPC error, silently reintroducing this bug.
 *
 * This file replaces that approach with a single, robust interception of the
 * network layer itself: we wrap window.fetch once, watch for calls to the
 * cart update endpoints, and update the header badge directly from the JSON
 * response our controllers already return (amount / cart_quantity), no
 * matter which code path triggered the update (core Odoo widgets, the
 * "Enlever du panier" button, or the custom "Add to cart" buttons on the
 * product pages).
 */
(function () {
    "use strict";

    var CART_ENDPOINTS = ["/shop/cart/update_json", "/shop/cart/update"];

    function isCartUpdateUrl(url) {
        if (!url) {
            return false;
        }
        var asString = typeof url === "string" ? url : (url.url || "");
        return CART_ENDPOINTS.some(function (endpoint) {
            return asString.indexOf(endpoint) !== -1;
        });
    }

    function formatAmount(amount) {
        var value = Number(amount) || 0;
        try {
            return (
                new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(value) +
                " CFA"
            );
        } catch (e) {
            return String(Math.round(value)) + " CFA";
        }
    }

    function updateHeaderBadge(data) {
        if (!data || typeof data !== "object") {
            return;
        }
        // JSON-RPC 2.0 wraps the actual payload in { jsonrpc, id, result: {...} }.
        var payload = "result" in data ? data.result : data;
        if (!payload || typeof payload !== "object") {
            return;
        }

        if (typeof payload.amount !== "undefined") {
            var amountEls = document.querySelectorAll(".my_cart_amount");
            amountEls.forEach(function (el) {
                el.textContent = formatAmount(payload.amount);
            });
        }

        if (typeof payload.cart_quantity !== "undefined") {
            var qtyEls = document.querySelectorAll(".my_cart_quantity");
            qtyEls.forEach(function (el) {
                el.textContent = payload.cart_quantity;
            });
        }
    }

    // Guard against double-patching if this script is somehow loaded twice.
    if (window.__emakhcCartFetchPatched) {
        return;
    }
    window.__emakhcCartFetchPatched = true;

    var originalFetch = window.fetch;
    window.fetch = function () {
        var args = arguments;
        var url = args[0];
        var result = originalFetch.apply(this, args);

        if (!isCartUpdateUrl(url)) {
            return result;
        }

        return result.then(function (response) {
            // Clone so we don't consume the body the caller still needs.
            response
                .clone()
                .json()
                .then(updateHeaderBadge)
                .catch(function () {
                    // Non-JSON or unreadable body: nothing to sync, ignore.
                });
            return response;
        });
    };

    // Some parts of Odoo's public widgets may still use jQuery.ajax / XHR
    // instead of fetch. Cover that path too, defensively.
    if (window.jQuery) {
        window.jQuery(document).ajaxSuccess(function (event, xhr, settings, data) {
            if (isCartUpdateUrl(settings && settings.url)) {
                updateHeaderBadge(data);
            }
        });
    }
})();