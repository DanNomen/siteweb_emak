/** @odoo-module **/

/**
 * Force la suppression COMPLETE d'une ligne de panier au clic sur le
 * bouton/lien "Enlever du panier" (classe .js_delete_product), quel que
 * soit le comportement par défaut d'Odoo ou d'autres modules (décrément,
 * etc.).
 *
 * On écoute en phase de capture (true) sur document afin de s'exécuter
 * AVANT les gestionnaires délégués standards de website_sale, puis on
 * bloque leur exécution (stopImmediatePropagation) pour n'avoir que
 * notre propre logique : toujours set_qty = 0.
 */
(function () {
    "use strict";

    function findProductId(el) {
        // La ligne peut être une <tr> (panier desktop) ou une div (mobile).
        var container = el.closest(".o_cart_product") || el.closest("tr") || el.parentElement;
        var depth = 0;
        while (container && depth < 6) {
            var withId = container.querySelector("[data-product-id]");
            if (withId) {
                return withId.getAttribute("data-product-id");
            }
            container = container.parentElement;
            depth += 1;
        }
        return null;
    }

    document.addEventListener(
        "click",
        function (ev) {
            var target = ev.target.closest(".js_delete_product");
            if (!target) {
                return;
            }

            ev.preventDefault();
            ev.stopPropagation();
            if (ev.stopImmediatePropagation) {
                ev.stopImmediatePropagation();
            }

            var productId = findProductId(target);
            if (!productId) {
                // Sécurité : si on ne trouve pas le produit, on recharge simplement
                // la page plutôt que de ne rien faire.
                window.location.reload();
                return;
            }

            fetch("/shop/cart/update_json", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        product_id: parseInt(productId, 10),
                        set_qty: 0,
                        display: true,
                    },
                }),
            })
                .catch(function () {
                    // Même en cas d'erreur réseau, on force le rechargement pour
                    // refléter l'état réel du panier côté serveur.
                })
                .then(function () {
                    window.location.reload();
                });
        },
        true
    );
})();
