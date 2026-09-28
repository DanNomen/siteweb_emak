(function () {
    'use strict';

    function isEmakmedSite() {
        const metaSite = document.querySelector('meta[name="emakmed-site"]');
        if (metaSite) return true;

        const hostname = window.location.hostname.toLowerCase();
        return !hostname.includes('emakhealthcare');
    }

    function hideStockTextElements() {
        if (!isEmakmedSite()) return;

        const candidates = document.body.querySelectorAll('div, span, p, small, td, b, strong');
        candidates.forEach(el => {
            const txt = el.textContent.trim();
            if (txt.includes('En stock') || txt.includes('Stock épuisé')) {
                // Must not be a parent container holding images, forms, inputs, buttons, links, or product cards
                if (!el.querySelector('img, button, input, a, form, table, .oe_product_cart, .row, .col, .container')) {
                    el.style.setProperty('display', 'none', 'important');
                }
            }
        });
    }

    function showStockAlert(message) {
        let modal = document.getElementById('emakmed_stock_alert_modal');

        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'emakmed_stock_alert_modal';
            modal.className = 'emakmed-stock-modal';
            modal.innerHTML = `
                <div class="emakmed-stock-modal-overlay" onclick="emakmedCloseStockAlert()">
                    <div class="emakmed-stock-modal-box" onclick="event.stopPropagation()">
                        <div class="emakmed-stock-modal-icon">
                            <i class="fa fa-exclamation-triangle"></i>
                        </div>
                        <h5 class="emakmed-stock-modal-title">Information sur la disponibilité</h5>
                        <p class="emakmed-stock-modal-message" id="emakmed_stock_alert_message"></p>
                        <button class="btn emakmed-stock-modal-close" onclick="emakmedCloseStockAlert()">
                            Compris
                        </button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        const msgEl = modal.querySelector('#emakmed_stock_alert_message') ||
                       modal.querySelector('.emakmed-stock-modal-message');
        if (msgEl) msgEl.textContent = message;
        modal.style.display = 'flex';

        clearTimeout(modal._autoCloseTimer);
        modal._autoCloseTimer = setTimeout(() => emakmedCloseStockAlert(), 8000);
    }

    window.emakmedCloseStockAlert = function () {
        const modal = document.getElementById('emakmed_stock_alert_modal');
        if (modal) {
            modal.style.display = 'none';
            clearTimeout(modal._autoCloseTimer);
        }
    };

    function showBootstrapAlert(message, type = 'warning') {
        let container = document.getElementById('emakmed_alerts_container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'emakmed_alerts_container';
            container.style.cssText = 'position:fixed;top:80px;right:20px;z-index:9999;min-width:350px;max-width:450px;';
            document.body.appendChild(container);
        }

        const alertId = 'alert_' + Date.now();
        const alertHtml = `
            <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show shadow-lg emakmed-stock-toast"
                 role="alert" style="border-left: 4px solid var(--bs-${type});">
                <div class="d-flex align-items-start gap-2">
                    <i class="fa fa-exclamation-triangle mt-1 flex-shrink-0"></i>
                    <div>
                        <strong class="d-block mb-1">Disponibilité du produit</strong>
                        <span>${message}</span>
                    </div>
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Fermer"></button>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', alertHtml);

        setTimeout(() => {
            const alertEl = document.getElementById(alertId);
            if (alertEl) {
                alertEl.classList.remove('show');
                setTimeout(() => alertEl.remove(), 300);
            }
        }, 6000);
    }

    function interceptCartForms() {
        if (!isEmakmedSite()) return;

        document.addEventListener('submit', function (e) {
            const form = e.target;
            if (!form || !form.action) return;
            if (!form.action.includes('/shop/cart/update')) return;
        });
    }

    function interceptAjaxCart() {
        if (!isEmakmedSite()) return;

        const originalOpen = XMLHttpRequest.prototype.open;
        const originalSend = XMLHttpRequest.prototype.send;

        XMLHttpRequest.prototype.open = function (method, url) {
            this._emakmed_url = url;
            return originalOpen.apply(this, arguments);
        };

        XMLHttpRequest.prototype.send = function (body) {
            if (this._emakmed_url && this._emakmed_url.includes('/shop/cart/update_json')) {
                const xhr = this;
                const originalOnload = xhr.onload;

                xhr.onload = function () {
                    if (originalOnload) originalOnload.apply(xhr, arguments);

                    try {
                        const response = JSON.parse(xhr.responseText);
                        if (response && response.notification_info && response.notification_info.warning) {
                            showBootstrapAlert(response.notification_info.warning, 'warning');
                        }
                    } catch (err) {
                    }
                };
            }
            return originalSend.apply(this, arguments);
        };

        if (window.fetch) {
            const originalFetch = window.fetch;
            window.fetch = function (url, options) {
                const promise = originalFetch.apply(this, arguments);

                if (url && url.toString().includes('/shop/cart/update_json')) {
                    return promise.then(response => {
                        const cloned = response.clone();
                        cloned.json().then(data => {
                            if (data && data.notification_info && data.notification_info.warning) {
                                showBootstrapAlert(data.notification_info.warning, 'warning');
                            }
                        }).catch(() => {});
                        return response;
                    });
                }
                return promise;
            };
        }
    }

    function checkSessionAlerts() {
        if (!isEmakmedSite()) return;

        const existingAlert = document.getElementById('emakmed_stock_alert');
        if (existingAlert) {
            existingAlert.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    function validateQtyBeforeSubmit() {
        if (!isEmakmedSite()) return;

        document.addEventListener('click', function (e) {
            const btn = e.target.closest('.a-submit, [data-action="o_website_sale_add_cart"]');
            if (!btn) return;

            const form = btn.closest('form[action*="/shop/cart/update"]');
            if (!form) return;

            const qtyInput = form.querySelector('input[name="add_qty"]');
            const qty = qtyInput ? parseInt(qtyInput.value) : 1;

            const maxQty = parseInt(form.dataset.maxQty || qtyInput?.dataset.maxQty || '0');

            if (maxQty > 0 && qty > maxQty) {
                e.preventDefault();
                e.stopPropagation();
                showBootstrapAlert(
                    `⚠️ La quantité disponible est limitée à ${maxQty} unité(s). Veuillez ajuster votre commande.`,
                    'warning'
                );
                if (qtyInput) qtyInput.value = maxQty;
                return false;
            }
        });
    }

    function init() {
        hideStockTextElements();
        interceptCartForms();
        interceptAjaxCart();
        checkSessionAlerts();
        validateQtyBeforeSubmit();

        const observer = new MutationObserver(hideStockTextElements);
        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
