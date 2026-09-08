/** @odoo-module **/
import { Component, useState } from "@odoo/owl";

/**
 * Barre de recherche unique (façon barre de recherche native Odoo) pour les
 * écrans de rapports de ce module : un seul champ texte, des suggestions
 * "Rechercher <Compte/Contact/Pièce> pour : <texte>" façon facettes Odoo, et
 * les critères choisis affichés comme des tags amovibles dans la barre.
 *
 * Émet `onSearch({account_search, partner_search, piece_search})` à chaque
 * changement (ajout ou suppression d'un tag) — un seul tag actif par
 * catégorie, un nouveau tag remplace l'ancien de la même catégorie.
 */

const TAG_DEFS = [
    { type: "account", label: "Compte" },
    { type: "partner", label: "Contact" },
    { type: "piece", label: "Pièce" },
];

export class ReportSearchBar extends Component {
    static template = "dynamic_accounts_report.ReportSearchBar";
    static props = {
        onSearch: Function,
    };

    setup() {
        this.tagDefs = TAG_DEFS;
        this.state = useState({
            query: "",
            showDropdown: false,
            values: { account: "", partner: "", piece: "" },
        });
    }

    get tags() {
        return this.tagDefs
            .filter((def) => this.state.values[def.type])
            .map((def) => ({ ...def, value: this.state.values[def.type] }));
    }

    onInput() {
        this.state.showDropdown = true;
    }

    onFocus() {
        this.state.showDropdown = true;
    }

    onBlur() {
        this.state.showDropdown = false;
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            if (this.state.query.trim()) {
                this.commit("account");
            }
        } else if (ev.key === "Escape") {
            this.state.showDropdown = false;
        }
    }

    commit(type) {
        const value = this.state.query.trim();
        if (!value) {
            return;
        }
        this.state.values[type] = value;
        this.state.query = "";
        this.state.showDropdown = false;
        this._emit();
    }

    removeTag(type) {
        this.state.values[type] = "";
        this._emit();
    }

    _emit() {
        this.props.onSearch({
            account_search: this.state.values.account || null,
            partner_search: this.state.values.partner || null,
            piece_search: this.state.values.piece || null,
        });
    }
}
