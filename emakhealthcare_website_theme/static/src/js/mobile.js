/** =============================================================
 *  EMAKHEALTHCARE — MOBILE JS
 *  Injecte la bottom nav bar et améliore l'UX mobile
 *  ============================================================= */

(function () {
    'use strict';

    // ── 1. Injecter la Bottom Navigation Bar ──────────────────────
    function injectBottomNav() {
        if (document.getElementById('emakhc-mobile-nav')) return;

        // Lire la quantité du panier depuis le badge existant
        var cartBadge = document.querySelector('.my_cart_quantity');
        var cartQty = cartBadge ? cartBadge.textContent.trim() : '0';

        // Détecter la page active
        var path = window.location.pathname;
        var activeAccueil = (path === '/' || path === '') ? 'active' : '';
        var activeProduits = path.startsWith('/produits') || path.startsWith('/shop') ? 'active' : '';
        var activePromos = path.startsWith('/promotions') ? 'active' : '';
        var activeReclamations = path.startsWith('/claim') ? 'active' : '';
        var activeCategories = path.startsWith('/categories') ? 'active' : '';
        var activeCompte = path.startsWith('/my') || path.startsWith('/web/login') ? 'active' : '';

        var nav = document.createElement('nav');
        nav.id = 'emakhc-mobile-nav';
        nav.setAttribute('aria-label', 'Navigation principale');

        nav.innerHTML = `
            <!-- Accueil -->
            <a href="/" class="emakhc-nav-item ${activeAccueil}" aria-label="Accueil">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                    <polyline points="9 22 9 12 15 12 15 22"/>
                </svg>
                <span>Accueil</span>
            </a>

            <!-- Produits -->
            <a href="/produits" class="emakhc-nav-item ${activeProduits}" aria-label="Produits">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                    <line x1="8" y1="21" x2="16" y2="21"/>
                    <line x1="12" y1="17" x2="12" y2="21"/>
                </svg>
                <span>Produits</span>
            </a>

            <!-- Promotions -->
            <a href="/promotions" class="emakhc-nav-item ${activePromos}" aria-label="Promotions">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 12 20 22 4 22 4 12"/>
                    <rect x="2" y="7" width="20" height="5"/>
                    <line x1="12" y1="22" x2="12" y2="7"/>
                    <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"/>
                    <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"/>
                </svg>
                <span>Promos</span>
            </a>

            <!-- Réclamations -->
            <a href="/claim/your_claims" class="emakhc-nav-item ${activeReclamations}" aria-label="Réclamations">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                    <polyline points="10 9 9 9 8 9"/>
                </svg>
                <span>Réclamations</span>
            </a>

            <!-- Panier -->
            <a href="/shop/cart" class="emakhc-nav-item" aria-label="Panier" id="emakhc-mobile-cart">
                <div style="position:relative;display:inline-block;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
                         stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="9" cy="21" r="1"/>
                        <circle cx="20" cy="21" r="1"/>
                        <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
                    </svg>
                    <span class="emakhc-cart-badge my_cart_quantity" id="emakhc-mobile-cart-badge">${cartQty}</span>
                </div>
                <span>Panier</span>
            </a>

            <!-- Store Selector -->
            <a href="#" class="emakhc-nav-item" id="emakhc-mobile-store-btn" aria-label="Store">
                <span id="emakhc-mobile-store-flag" style="font-size:1.4rem;line-height:1;">&#x1F1F2;&#x1F1F1;</span>
                <span style="font-size:0.65rem;">Store</span>
            </a>

            <!-- Espace client -->
            <a href="/my" class="emakhc-nav-item ${activeCompte}" aria-label="Espace client">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                </svg>
                <span>Mon compte</span>
            </a>
        `;

        document.body.appendChild(nav);

        // Modal de sélection du store
        var storeModal = document.createElement('div');
        storeModal.id = 'emakhc-store-modal';
        storeModal.style.cssText = [
            'display:none', 'position:fixed', 'bottom:75px', 'left:50%',
            'transform:translateX(-50%)', 'background:#fff', 'border-radius:16px',
            'box-shadow:0 8px 32px rgba(0,0,0,0.18)', 'z-index:10000',
            'padding:18px 24px', 'min-width:260px',
        ].join(';');
        storeModal.innerHTML = [
            '<div style="font-weight:700;font-size:0.95rem;margin-bottom:14px;color:#111827;">Choisir votre store</div>',
            '<a href="/shop/change_store?store_country=Mali" style="display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:10px;text-decoration:none;color:#111827;border:1px solid #e5e7eb;margin-bottom:8px;">',
            '  <span style="font-size:1.5rem;">&#x1F1F2;&#x1F1F1;</span>',
            '  <span style="font-weight:600;font-size:0.9rem;">Mali</span>',
            '</a>',
            '<a href="/shop/change_store?store_country=CI" style="display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:10px;text-decoration:none;color:#111827;border:1px solid #e5e7eb;">',
            '  <span style="font-size:1.5rem;">&#x1F1E8;&#x1F1EE;</span>',
            '  <span style="font-weight:600;font-size:0.9rem;">C\u00f4te d\'Ivoire</span>',
            '</a>',
        ].join('');
        document.body.appendChild(storeModal);

        // Toggle modal au clic sur le bouton Store
        var storeBtn = document.getElementById('emakhc-mobile-store-btn');
        if (storeBtn) {
            storeBtn.addEventListener('click', function(e) {
                e.preventDefault();
                storeModal.style.display = storeModal.style.display === 'none' ? 'block' : 'none';
            });
        }

        // Fermer le modal en cliquant ailleurs
        document.addEventListener('click', function(e) {
            if (!storeModal.contains(e.target) && e.target !== storeBtn && !storeBtn.contains(e.target)) {
                storeModal.style.display = 'none';
            }
        });
    }

    // ── 2. Synchroniser le badge panier ──────────────────────────
    function syncCartBadge() {
        var mobileBadge = document.getElementById('emakhc-mobile-cart-badge');
        var desktopBadge = document.querySelector('header .my_cart_quantity');
        if (!mobileBadge || !desktopBadge) return;

        // Observer les changements sur le badge desktop
        var observer = new MutationObserver(function () {
            mobileBadge.textContent = desktopBadge.textContent.trim();
        });
        observer.observe(desktopBadge, { childList: true, characterData: true, subtree: true });
    }

    // ── 3. Améliorer les offres spéciales : scroll horizontal ────
    function makeOffersScrollable() {
        if (window.innerWidth > 768) return;

        // Chercher la ligne d'offres spéciales (section avec PROMOTION badge)
        var offersSection = document.querySelector('section .row.g-3');
        if (!offersSection) return;

        // Vérifier qu'il s'agit bien des offres (badge PROMOTION présent)
        var hasBadge = offersSection.querySelector('.badge');
        if (!hasBadge) return;

        offersSection.classList.add('emakhc-offers-row-mobile');
    }

    // ── 4. Touch feedback sur les cartes ─────────────────────────
    function addTouchFeedback() {
        if (window.innerWidth > 768) return;

        document.querySelectorAll('.card').forEach(function (card) {
            card.addEventListener('touchstart', function () {
                card.style.transform = 'scale(0.97)';
                card.style.boxShadow = '0 2px 8px rgba(0,0,0,.08)';
            }, { passive: true });
            card.addEventListener('touchend', function () {
                card.style.transform = '';
                card.style.boxShadow = '';
            }, { passive: true });
        });
    }

    // ── 5. Améliorer la barre de recherche mobile ────────────────
    function improveSearchModal() {
        if (window.innerWidth > 768) return;

        // Ouvrir la modal de recherche en cliquant sur le header
        var searchIcon = document.querySelector('header a[data-bs-target="#searchModalEmakhc"]');
        if (searchIcon) {
            searchIcon.addEventListener('click', function () {
                setTimeout(function () {
                    var input = document.querySelector('#searchModalEmakhc input');
                    if (input) input.focus();
                }, 300);
            });
        }
    }

    // ── 6. Initialisation ────────────────────────────────────────
    function init() {
        injectBottomNav();
        syncCartBadge();
        makeOffersScrollable();
        addTouchFeedback();
        improveSearchModal();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Réinitialiser lors des navigations Odoo (SPA-like)
    window.addEventListener('popstate', function () {
        setTimeout(init, 100);
    });

})();
