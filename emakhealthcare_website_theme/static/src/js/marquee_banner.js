/**
 * Emakhealthcare – Trust Benefits Marquee
 * Ajuste dynamiquement la durée de l'animation selon la largeur réelle
 * de la piste, pour garantir une vitesse constante sur toutes les résolutions.
 */
(function () {
    'use strict';

    const PIXELS_PER_SECOND = 55; // vitesse de défilement px/s

    function initMarquee() {
        const bar = document.querySelector('.emakhc-marquee-bar');
        if (!bar) return;

        const track = bar.querySelector('.emakhc-marquee-track');
        if (!track) return;

        // La piste contient deux copies du contenu (pour boucle seamless).
        // On mesure la largeur d'une seule copie = la moitié de la piste complète.
        const clone = track.cloneNode(false);
        Object.assign(clone.style, { visibility: 'hidden', position: 'absolute', top: '-9999px', whiteSpace: 'nowrap' });
        // Remplir le clone avec les enfants de la première moitié (avant duplication)
        document.body.appendChild(clone);
        clone.innerHTML = track.innerHTML;
        const singleWidth = clone.scrollWidth;
        document.body.removeChild(clone);

        // Durée proportionnelle à la largeur
        const duration = Math.max(singleWidth / PIXELS_PER_SECOND, 8);
        track.style.animationDuration = duration.toFixed(2) + 's';
    }

    // Lancer après chargement du DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initMarquee);
    } else {
        initMarquee();
    }

    // Réajuster si la fenêtre est redimensionnée
    let resizeTimer;
    window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(initMarquee, 200);
    });
})();
