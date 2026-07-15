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
        var $tbody = this.$('.purchase_tbody');
        this.$('#claim_table').removeClass('d-none');
        $tbody.empty();

        lines.forEach(function (line) {
            var $row = $('<tr>');

            // Colonne Sélection
            $row.append($('<td>').append(
                $('<input>', {
                    type: 'checkbox',
                    class: 'form-check-input',
                    name: `selection_${line.id}`,
                })
            ));

            // Colonne Produit
            $row.append($('<td class="text-start">').append(
                $('<input>', {
                    type: 'text',
                    class: 'form-control',
                    name: `name_${line.id}`,
                    value: line.name,
                    readonly: true
                })
            ));

            // Colonne Motif
            var $select = $('<select>', {
                class: 'form-control',
                name: 'reason_' + line.id
            });
            var reasons = line.reasons
            $.each(reasons, function (value, text) {
                $select.append($('<option>', {
                    value: value,
                    text: text
                }));
            });
            $row.append($('<td class="text-start">').append($select));


            // Colonne Quantité avec boutons - et +
            var $qtyInput = $('<input>', {
                type: 'text',
                class: 'form-control text-center qty-input',
                name: 'qty_' + line.id,
                value: 1,
                min: 1,
                max: line.qty || 1,
                'data-max': line.qty || 1
            });

            var $btnDecrement = $('<button>', {
                type: 'button',
                class: 'btn btn-outline-secondary qty-btn-decrement',
                text: '-',
                'data-line-id': line.id
            });

            var $btnIncrement = $('<button>', {
                type: 'button',
                class: 'btn btn-outline-secondary qty-btn-increment',
                text: '+',
                'data-line-id': line.id
            });

            var $inputGroup = $('<div>', {
                class: 'input-group',
                style: 'width: 120px'
            }).append($btnDecrement).append($qtyInput).append($btnIncrement);

            $row.append($('<td>').append($inputGroup));

            $tbody.append($row);
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
