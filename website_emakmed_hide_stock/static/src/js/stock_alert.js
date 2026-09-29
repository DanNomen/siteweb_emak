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
                            <span style="font-size: 2.2rem;">🔴</span>
                        </div>
                        <h5 class="emakmed-stock-modal-title" style="color: #dc3545; font-weight: 700;">RUPTURE DE STOCK</h5>
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
        modal._autoCloseTimer = setTimeout(() => emakmedCloseStockAlert(), 10000);
    }

    window.emakmedCloseStockAlert = function () {
        const modal = document.getElementById('emakmed_stock_alert_modal');
        if (modal) {
            modal.style.display = 'none';
            clearTimeout(modal._autoCloseTimer);
        }
    };

    function interceptCartForms() {
        if (!isEmakmedSite()) return;

        document.addEventListener('click', function (e) {
            const btn = e.target.closest('.a-submit, .emakmed-btn-out-of-stock, [data-out-of-stock="true"]');
            if (!btn) return;

            const form = btn.closest('form[action*="/shop/cart/update"]') || btn.closest('.oe_product_cart');
            const isOutOfStock = (btn.dataset.outOfStock === 'true') ||
                                (form && form.dataset.outOfStock === 'true') ||
                                btn.classList.contains('emakmed-btn-out-of-stock');

            if (isOutOfStock) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();

                const productName = btn.dataset.productName ||
                                  (form ? form.dataset.productName : '') ||
                                  'ce produit';

                showStockAlert(`🔴 RUPTURE DE STOCK : Le produit "${productName}" est actuellement en rupture de stock. Vous ne pouvez pas l'ajouter au panier.`);
                return false;
            }
        }, true);

        document.addEventListener('submit', function (e) {
            const form = e.target;
            if (!form || !form.action) return;
            if (!form.action.includes('/shop/cart/update')) return;

            if (form.dataset.outOfStock === 'true') {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();

                const productName = form.dataset.productName || 'ce produit';
                showStockAlert(`🔴 RUPTURE DE STOCK : Le produit "${productName}" est actuellement en rupture de stock. Vous ne pouvez pas l'ajouter au panier.`);
                return false;
            }
        }, true);
    }

    function disableQtyButtonsForOutOfStock() {
        if (!isEmakmedSite()) return;

        document.addEventListener('click', function (e) {
            const qtyBtn = e.target.closest('.emakmed-qty-disabled, [data-out-of-stock="true"] .btn');
            if (qtyBtn) {
                e.preventDefault();
                e.stopPropagation();
                return false;
            }
        }, true);
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
            if (this._emakmed_url && (this._emakmed_url.includes('/shop/cart/update') || this._emakmed_url.includes('/shop/cart/update_json'))) {
                const xhr = this;
                const originalOnload = xhr.onload;

                xhr.onload = function () {
                    if (originalOnload) originalOnload.apply(xhr, arguments);

                    try {
                        const response = JSON.parse(xhr.responseText);
                        const warning = response?.warning || response?.notification_info?.warning;
                        if (warning) {
                            showStockAlert(warning);
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

                if (url && (url.toString().includes('/shop/cart/update') || url.toString().includes('/shop/cart/update_json'))) {
                    return promise.then(response => {
                        const cloned = response.clone();
                        cloned.json().then(data => {
                            const warning = data?.warning || data?.notification_info?.warning;
                            if (warning) {
                                showStockAlert(warning);
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

    function init() {
        hideStockTextElements();
        interceptCartForms();
        disableQtyButtonsForOutOfStock();
        interceptAjaxCart();
        checkSessionAlerts();

        const observer = new MutationObserver(hideStockTextElements);
        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
