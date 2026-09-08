/** @odoo-module */
const { Component } = owl;
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useRef, useState } from "@odoo/owl";
import { BlockUI } from "@web/core/ui/block_ui";
import { download } from "@web/core/network/download";
import { formatFloat } from "@web/core/utils/numbers";
import { ReportSearchBar } from "@dynamic_accounts_report/js/report_search_bar";
const actionRegistry = registry.category("actions");
const today = luxon.DateTime.now();

class AgedReceivable extends owl.Component {
    static components = { ReportSearchBar };
    async setup() {
        super.setup(...arguments);
        this.initial_render = true;
        this.orm = useService('orm');
        this.action = useService('action');
        this.tbody = useRef('tbody');
        this.date_range = useRef('date_to');
        this.unfoldButton = useRef('unfoldButton');
        this.state = useState({
            move_line: null,
            data: null,
            total: null,
            currency: null,
            total_debit: null,
            diff0_sum: null,
            diff1_sum: null,
            diff2_sum: null,
            diff3_sum: null,
            diff4_sum: null,
            diff5_sum: null,
            selected_partner: [],
            selected_partner_rec: [],
            account_search: '',
            partner_search: '',
            piece_search: '',
        });
        this.load_data(self.initial_render = true);
    }
        async load_data() {
        /**
         * Loads totals only (fast). Lines are lazy-loaded on click.
         */
        var self = this;
        try {
            const data = await self.orm.call("age.receivable.report", "view_report", []);
            self._processData(data);
        } catch (el) {
            console.error('load_data error:', el);
        }
    }

    formatNumberWithSeparators(number) {
        const parsedNumber = parseFloat(number);
        if (isNaN(parsedNumber)) {
            return "0"; // Fallback to 0 if the input is invalid
        }
        // Whole numbers with a space as the thousands separator (e.g.
        // "1 000 000"), no decimals and no currency symbol.
        return Math.round(parsedNumber).toLocaleString('fr-FR');
    }

    _processData(data) {
        /** Process partner totals from backend response */
        const partner_totals = data.partner_totals || {};
        let diff0 = 0, diff1 = 0, diff2 = 0, diff3 = 0, diff4 = 0, diff5 = 0, total = 0;
        let currency = null;

        Object.values(partner_totals).forEach(p => {
            currency = p.currency_id || currency;
            diff0 += p.diff0_sum || 0;
            diff1 += p.diff1_sum || 0;
            diff2 += p.diff2_sum || 0;
            diff3 += p.diff3_sum || 0;
            diff4 += p.diff4_sum || 0;
            diff5 += p.diff5_sum || 0;
            total += p.debit_sum || 0;
            // The template reads these '_display' fields for every
            // partner row - they were never computed, so the 1-30/31-60/.../
            // Total columns always rendered blank for every partner.
            p.diff0_sum_display = this.formatNumberWithSeparators(p.diff0_sum || 0);
            p.diff1_sum_display = this.formatNumberWithSeparators(p.diff1_sum || 0);
            p.diff2_sum_display = this.formatNumberWithSeparators(p.diff2_sum || 0);
            p.diff3_sum_display = this.formatNumberWithSeparators(p.diff3_sum || 0);
            p.diff4_sum_display = this.formatNumberWithSeparators(p.diff4_sum || 0);
            p.diff5_sum_display = this.formatNumberWithSeparators(p.diff5_sum || 0);
            p.debit_sum_display = this.formatNumberWithSeparators(p.debit_sum || 0);
            // Lazy loading state
            p._lines_loaded = false;
            p._lines = [];
            p._expanded = false;
            p._loading = false;
        });

        this.state.move_line = data.partners || Object.keys(partner_totals);
        this.state.total = partner_totals;
        this.state.currency = currency;
        this.state.total_debit = total;
        this.state.total_debit_display = this.formatNumberWithSeparators(total);
        this.state.diff0_sum = diff0;
        this.state.diff0_sum_display = this.formatNumberWithSeparators(diff0);
        this.state.diff1_sum = diff1;
        this.state.diff1_sum_display = this.formatNumberWithSeparators(diff1);
        this.state.diff2_sum = diff2;
        this.state.diff2_sum_display = this.formatNumberWithSeparators(diff2);
        this.state.diff3_sum = diff3;
        this.state.diff3_sum_display = this.formatNumberWithSeparators(diff3);
        this.state.diff4_sum = diff4;
        this.state.diff4_sum_display = this.formatNumberWithSeparators(diff4);
        this.state.diff5_sum = diff5;
        this.state.diff5_sum_display = this.formatNumberWithSeparators(diff5);
    }

    async expandPartner(ev, partnerName) {
        /** Lazy-load aged lines for a single partner on click */
        ev.preventDefault();
        const partner = this.state.total[partnerName];
        if (!partner) return;
        if (partner._lines_loaded) {
            partner._expanded = !partner._expanded;
            return;
        }
        partner._loading = true;
        try {
            const lines = await this.orm.call(
                "age.receivable.report", "get_partner_aged_lines",
                [partner.partner_id, this.state.date_range || null]
            );
            partner._lines = lines;
            partner._lines_loaded = true;
            partner._expanded = true;
        } catch (e) {
            console.error('Failed to load aged lines for', partnerName, e);
        } finally {
            partner._loading = false;
        }
    }

    /**
     * Callback de <ReportSearchBar/> : reçoit les 3 critères courants
     * (compte / contact / pièce) à chaque ajout/suppression de tag, puis
     * relance la même recherche que les autres filtres (applyFilter,
     * appelé sans data-value ne fait que relancer l'appel RPC final avec
     * l'état courant). Note l'ordre des arguments propre à ce rapport :
     * applyFilter(ev, e, is_delete) et non applyFilter(val, ev, is_delete).
     */
    onReportSearch(payload) {
        this.state.account_search = payload.account_search || '';
        this.state.partner_search = payload.partner_search || '';
        this.state.piece_search = payload.piece_search || '';
        this.applyFilter({}, null);
    }
    async printPdf(ev) {
        /**
         * Generates and displays a PDF report for the partner ledger.
         *
         * @param {Event} ev - The event object triggered by the action.
         * @returns {Promise} - A promise that resolves to the result of the action.
         */
        ev.preventDefault();
        var self = this;
        var action_title = self.props.action.display_name;
        let totals = {
            'diff0_sum':this.state.diff0_sum,
            'diff0_sum_display':this.state.diff0_sum_display,
            'diff1_sum':this.state.diff1_sum,
            'diff1_sum_display':this.state.diff1_sum_display,
            'diff2_sum':this.state.diff2_sum,
            'diff2_sum_display':this.state.diff2_sum_display,
            'diff3_sum':this.state.diff3_sum,
            'diff3_sum_display':this.state.diff3_sum_display,
            'diff4_sum':this.state.diff4_sum,
            'diff4_sum_display':this.state.diff4_sum_display,
            'diff5_sum':this.state.diff5_sum,
            'diff5_sum_display':this.state.diff5_sum_display,
            'total_debit':this.state.total_debit,
            'total_debit_display':this.state.total_debit_display,
            'currency':this.state.currency,
        }
        // Aged lines are only lazy-loaded for a single partner when its row
        // is expanded (expandPartner/get_partner_aged_lines) - state.data
        // was declared but never populated, so the PDF always had partner
        // totals but zero aged-line detail. The server fetches the lines
        // itself in IrActionsReportAgedReceivable._get_report_values from
        // just the totals (which already carry each partner_id) and the
        // date filter below.
        return self.action.doAction({
            'type': 'ir.actions.report',
            'report_type': 'qweb-pdf',
            'report_name': 'dynamic_accounts_report.aged_receivable',
            'report_file': 'dynamic_accounts_report.aged_receivable',
            'data': {
                'move_lines': self.state.move_line,
                'total': self.state.total,
                'filters': this.filter(),
                'grand_total': totals,
                'title': action_title,
                'report_name': self.props.action.display_name,
                'date': this.date_range.el.value || null,
                'account_search': this.state.account_search || null,
                'piece_search': this.state.piece_search || null,
            },
            'display_name': self.props.action.display_name,
        });
    }
    filter() {
        let filters = {
            'partner': this.state.selected_partner_rec,
            'end_date': this.date_range.el.value,
        };
        return filters
    }
    async print_xlsx() {
        /**
         * Generates and downloads an XLSX report for the partner ledger.
         */
        var self = this;
        var action_title = self.props.action.display_name;
        let totals = {
            'diff0_sum':this.state.diff0_sum,
            'diff1_sum':this.state.diff1_sum,
            'diff2_sum':this.state.diff2_sum,
            'diff3_sum':this.state.diff3_sum,
            'diff4_sum':this.state.diff4_sum,
            'diff5_sum':this.state.diff5_sum,
            'total_debit':this.state.total_debit,
        }
        // get_xlsx_report() reads the partner list from the 'partners' key
        // (not 'move_lines') and only needs totals ('total') - it never
        // reads 'data' (no per-partner line detail in this export), so
        // that key doesn't need to be sent at all.
        var datas = {
            'partners': self.state.move_line,
            'total': self.state.total,
            'filters': this.filter(),
            'grand_total': totals,
            'title': action_title,
        }
        var action = {
            'data': {
                'model': 'age.receivable.report',
                'data': JSON.stringify(datas),
                'output_format': 'xlsx',
                'report_action': self.props.action.xml_id,
                'report_name': action_title,
            },
        };
        BlockUI;
        await download({
            url: '/xlsx_report',
            data: action.data,
            complete: () => unblockUI,
            error: (error) => self.call('crash_manager', 'rpc_error', error),
        });
    }
    async applyFilter(ev, e, is_delete = false) {
        if (ev.target && ev.target.attributes["data-value"]) {
            if (ev.target.attributes["data-value"].value == 'today') {
                this.date_range.el.value = today.toFormat('yyyy-MM-dd')
            } else if (ev.target.attributes["data-value"].value == 'last-month-end') {
                this.date_range.el.value = today.startOf('month').minus({ days: 1 }).toFormat('yyyy-MM-dd')
            } else if (ev.target.attributes["data-value"].value == 'last-quarter-end') {
                this.date_range.el.value = today.startOf('quarter').minus({ days: 1 }).toFormat('yyyy-MM-dd')
            } else if (ev.target.attributes["data-value"].value == 'last-year-end') {
                this.date_range.el.value = today.startOf('year').minus({ days: 1 }).toFormat('yyyy-MM-dd')
            }
        } else if (e && e.input && e.input.attributes.placeholder.value == 'Partner' && !is_delete) {
            this.state.selected_partner.push(ev[0].id)
            this.state.selected_partner_rec.push(ev[0])
        } else if (is_delete) {
            let index = this.state.selected_partner_rec.indexOf(ev)
            this.state.selected_partner_rec.splice(index, 1)
            this.state.selected_partner = this.state.selected_partner_rec.map((rec) => rec.id)
        }
        let filtered_data = await this.orm.call("age.receivable.report", "get_filter_values", [this.date_range.el.value, this.state.selected_partner, this.state.account_search, this.state.partner_search, this.state.piece_search]);
        this._processData(filtered_data);
    }
    openPartner(ev) {
        /** Opens the partner form view based on the selected event target. */
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: 'res.partner',
            res_id: parseInt(ev.target.attributes["data-id"].value, 10),
            views: [[false, "form"]],
            target: "current",
        });
    }
    gotoJournalItem(ev) {
        /** Opens the journal items list view for the selected partner's receivable lines. */
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: 'account.move.line',
            name: "Journal Items",
            views: [[false, "list"]],
            domain: [
                ["partner_id", "=", parseInt(ev.target.attributes["data-id"].value, 10)],
                ['account_type', '=', 'asset_receivable'],
            ],
            target: "current",
        });
    }
    getDomain() {
        return [];
    }
}
AgedReceivable.template = 'age_r_template_new';
AgedReceivable.defaultProps = {
    resIds: [],
};

AgedReceivable.props = ['*'];
actionRegistry.add("age_r", AgedReceivable);
