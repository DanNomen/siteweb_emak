/** @odoo-module **/

import publicWidget from 'web.public.widget';
import { debounce } from "@web/core/utils/timing";

publicWidget.registry.EmakhcAnimatedMenu = publicWidget.Widget.extend({
    selector: '.emakhc-animated-menu',
    events: {
        'mouseenter .nav-item': '_onMouseEnterItem',
        'mouseleave': '_onMouseLeaveMenu',
    },

    start: function () {
        this.underline = this.$('.menu-sliding-underline');
        this.navItems = this.$('.nav-item');
        this.activeItem = null;

        // Determine active item based on URL
        var path = window.location.pathname;
        var exactMatches = [];
        var partialMatches = [];

        this.$('.nav-link').each(function () {
            var href = $(this).attr('href');
            if (href && href !== '#') {
                // Normalize hrefs for comparison
                var hrefPath = href.split('?')[0];
                if (path === hrefPath) {
                    exactMatches.push($(this).closest('.nav-item'));
                } else if (hrefPath !== '/' && path.startsWith(hrefPath)) {
                    partialMatches.push($(this).closest('.nav-item'));
                }
            }
        });

        if (exactMatches.length > 0) {
            this.activeItem = exactMatches[0];
        } else if (partialMatches.length > 0) {
            // Find longest partial match
            partialMatches.sort((a, b) => b.find('.nav-link').attr('href').length - a.find('.nav-link').attr('href').length);
            this.activeItem = partialMatches[0];
        }

        if (this.activeItem) {
            this.activeItem.find('.nav-link').addClass('active-emak');
            // Give layout a moment to render before positioning
            setTimeout(() => {
                this._moveUnderline(this.activeItem);
            }, 50);
        }

        // Also re-position on window resize
        var self = this;
        $(window).on('resize.emakhc_menu', debounce(function () {
            if (self.activeItem) {
                self._moveUnderline(self.activeItem);
            } else {
                self.underline.css({ width: 0, opacity: 0 });
            }
        }, 100));

        return this._super.apply(this, arguments);
    },

    destroy: function () {
        $(window).off('resize.emakhc_menu');
        this._super.apply(this, arguments);
    },

    _moveUnderline: function ($item) {
        var $link = $item.find('.nav-link');
        if ($link.length) {
            var position = $link.position();
            // Dropdown links sometimes have unpredictable widths, use scrollWidth
            var width = $link[0].scrollWidth; 
            
            // Adjust for padding if needed, but usually exact width of link is fine
            this.underline.css({
                left: position.left + 'px',
                width: width + 'px',
                opacity: 1
            });
        }
    },

    _onMouseEnterItem: function (ev) {
        var $item = $(ev.currentTarget);
        this._moveUnderline($item);
        
        // Remove active class from all, add to hovered
        this.$('.nav-link').removeClass('active-emak');
        $item.find('> .nav-link').addClass('active-emak');
    },

    _onMouseLeaveMenu: function () {
        this.$('.nav-link').removeClass('active-emak');
        if (this.activeItem) {
            this._moveUnderline(this.activeItem);
            this.activeItem.find('> .nav-link').addClass('active-emak');
        } else {
            this.underline.css({ width: 0, opacity: 0 });
        }
    },
});
