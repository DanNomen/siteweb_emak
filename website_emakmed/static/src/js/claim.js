/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.ClaimReclamation = publicWidget.Widget.extend({
    selector: "#reclamationForm",
    events: {
        'click #find_invoice_btn': '_onClickSearchInvoice',
        'click .qty-btn-decrement': '_onClickDecrement',
        'click .qty-btn-increment': '_onClickIncrement',
        // 'click #submit_btn': '_onClickSubmitBtnClaim',
    },

    async fetchInvoiceLines(invoiceNumber) {
        try {
            const results = await rpc("/get_invoice_lines", { name: invoiceNumber });
            if (!results) {
                const msg = "Erreur lors de la récupération des produits.";
                this._showMessage(msg)
            }
            if (results.lines) {
                this.displayInvoiceLines(results.lines);
            } else {
                const msg = "Aucun produit trouvé pour cette facture.";
                this._showMessage(msg)
            }
        } catch (error) {
            const msg = "Erreur lors de la récupération des produits.";
            this._showMessage(msg)
        }
    },

    displayInvoiceLines(lines) {
        var $container = this.$('.purchase_tbody');
        this.$('#claim_table').show();
        $container.empty();

        lines.forEach(function (line) {
            // Carte Bootstrap pour chaque produit (responsive sur mobile ET desktop)
            var $card = $('<div>', {
                class: 'card mb-3 shadow-sm border-0',
                style: 'border-left: 4px solid #38A935 !important;'
            });

            var $cardBody = $('<div>', { class: 'card-body p-3' });

            // En-tête : case à cocher + nom du produit
            var $header = $('<div>', { class: 'd-flex align-items-center gap-2 mb-3 pb-2 border-bottom' });
            $header.append($('<input>', {
                type: 'checkbox',
                class: 'form-check-input flex-shrink-0',
                name: `selection_${line.id}`,
            }));
            $header.append($('<strong>', { class: 'text-dark', text: line.name }));
            $cardBody.append($header);

            // Ligne Motif
            var $select = $('<select>', {
                class: 'form-select form-select-sm',
                name: 'reason_' + line.id
            });
            var reasons = line.reasons;
            $.each(reasons, function (value, text) {
                $select.append($('<option>', { value: value, text: text }));
            });
            var $motifRow = $('<div>', { class: 'd-flex justify-content-between align-items-center mb-2' });
            $motifRow.append($('<span>', { class: 'text-muted fw-semibold small', text: 'Motif' }));
            $motifRow.append($('<div>', { class: 'ms-2 flex-grow-1' }).append($select));
            $cardBody.append($motifRow);

            // Ligne Quantité
            var $qtyInput = $('<input>', {
                type: 'text',
                class: 'form-control form-control-sm text-center qty-input',
                name: 'qty_' + line.id,
                value: 1,
                min: 1,
                max: line.qty || 1,
                'data-max': line.qty || 1,
                style: 'width: 50px;'
            });
            var $btnDecrement = $('<button>', {
                type: 'button',
                class: 'btn btn-outline-secondary btn-sm qty-btn-decrement',
                text: '-',
                'data-line-id': line.id
            });
            var $btnIncrement = $('<button>', {
                type: 'button',
                class: 'btn btn-outline-secondary btn-sm qty-btn-increment',
                text: '+',
                'data-line-id': line.id
            });
            var $inputGroup = $('<div>', { class: 'input-group input-group-sm', style: 'width: 110px;' })
                .append($btnDecrement).append($qtyInput).append($btnIncrement);

            var $qtyRow = $('<div>', { class: 'd-flex justify-content-between align-items-center' });
            $qtyRow.append($('<span>', { class: 'text-muted fw-semibold small', text: 'Quantité' }));
            $qtyRow.append($inputGroup);
            $cardBody.append($qtyRow);

            $card.append($cardBody);
            $container.append($card);
        });

        if (lines.length > 0) {
            this.$('#message_field').show();
            this.$('#submit_btn').show();
        }
    },

    async _onClickSearchInvoice() {
        const invoiceNumber = this.el.querySelector("#invoice_number").value;
        if (!invoiceNumber) {
            const msg = "Veuillez entrer un numéro de facture valide.";
            this._showMessage(msg)
            return;
        }
        this.fetchInvoiceLines(invoiceNumber)
    },

    _onClickSubmitBtnClaim() {
        // trouver tous les valeur du checkbox checked(on)ici
        const checkedLines = this.el.querySelectorAll('.select-line:checked');

    },

    _onClickDecrement(ev) {
        ev.preventDefault();
        var lineId = ev.target.getAttribute('data-line-id');
        var $input = this.$('input[name="qty_' + lineId + '"]');
        var currentValue = parseInt($input.val()) || 1;
        var minValue = parseInt($input.attr('min')) || 1;

        if (currentValue > minValue) {
            $input.val(currentValue - 1);
        }
    },

    _onClickIncrement(ev) {
        ev.preventDefault();
        var lineId = ev.target.getAttribute('data-line-id');
        var $input = this.$('input[name="qty_' + lineId + '"]');
        var currentValue = parseInt($input.val()) || 1;
        var maxValue = parseInt($input.attr('data-max')) || parseInt($input.attr('max')) || 1;

        if (currentValue < maxValue) {
            $input.val(currentValue + 1);
        }
    },

    _showMessage(msg) {
        const spanShow = this.el.querySelector("#invoice_number_error");
        spanShow.replaceChildren(document.createTextNode(msg));
        setTimeout(() => {
            spanShow.replaceChildren(document.createTextNode(""));
        }, 5000);
    }
})
