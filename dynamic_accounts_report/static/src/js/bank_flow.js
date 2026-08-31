/** @odoo-module */
const { Component } = owl;
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useRef, useState } from "@odoo/owl";
import { BlockUI } from "@web/core/ui/block_ui";
import { download } from "@web/core/network/download";
const actionRegistry = registry.category("actions");

class BankBook extends owl.Component {
    async setup() {
        super.setup(...arguments);
        this.initial_render = true;
        this.orm = useService('orm');
        this.action = useService('action');
        this.dialog = useService("dialog");
        this.tbody = useRef('tbody');
        this.unfoldButton = useRef('unfoldButton');
        this.state = useState({
            move_line: null,
            data: null,
            total: null,
            accounts: null,
            filter_applied: null,
            selected_partner: [],
            selected_partner_rec: [],
            date_range: null,
            date_label: null,
            options: null,
            selected_account_list: [],
            total_debit: null,
            total_debit_display: null,
            total_credit: null,
            total_credit_display: null,
            currency: null,
            message_list : [],
        });
        this.load_data(self.initial_render = true);

    }
    formatNumberWithSeparators(number) {
        const parsedNumber = parseFloat(number);
        if (isNaN(parsedNumber)) {
            return "0.00"; // Fallback to 0.00 if the input is invalid
        }
        return parsedNumber.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }
    async load_data() {
        /**
         * Loads the data for the bank book report.
         */
        var self = this;
        try {
            const data = await self.orm.call("bank.book.report", "view_report", []);
            self._processAccountData(data);
            // Build the full account picker list once, from the unfiltered initial load
            // (applyFilter must NOT overwrite this or the picker would shrink to only
            // the currently-matching accounts, making it impossible to broaden the filter again).
            self.state.accounts = Object.entries(data['account_totals'] || {}).map(([name, acc]) => ({
                id: acc.account_id, name: name, display_name: name,
            }));
        }
        catch (el) {
            console.error('BankBook load_data error:', el);
        }
    }
    _processAccountData(data) {
        /**
         * The backend (bank.book.report) returns {account_totals: {name: {...}}, accounts: [name, ...]}.
         * Build state.account_data (keyed by account name, used by the template for
         * both the row totals and the lazy-loaded expand/collapse detail lines) and
         * state.move_line (the ordered list of account names to iterate over).
         */
        const account_totals = data['account_totals'] || {};
        let totalDebitSum = 0;
        let totalCreditSum = 0;
        let currency = null;

        Object.values(account_totals).forEach(acc => {
            currency = acc.currency_id || currency;
            totalDebitSum += acc.total_debit || 0;
            totalCreditSum += acc.total_credit || 0;
            acc.total_debit_display = this.formatNumberWithSeparators(acc.total_debit || 0);
            acc.total_credit_display = this.formatNumberWithSeparators(acc.total_credit || 0);
            acc.balance_display = ((acc.total_debit || 0) - (acc.total_credit || 0)).toFixed(2);
            acc._lines_loaded = false;
            acc._lines = [];
        });

        this.state.account_data = account_totals;
        this.state.move_line = data['accounts'] || Object.keys(account_totals);
        if (currency) { this.state.currency = currency; }
        this.state.total_debit = totalDebitSum.toFixed(2);
        this.state.total_debit_display = this.formatNumberWithSeparators(totalDebitSum);
        this.state.total_credit = totalCreditSum.toFixed(2);
        this.state.total_credit_display = this.formatNumberWithSeparators(totalCreditSum);
    }
    async expandAccount(ev, accountName) {
        /** Lazy-load move lines for a single account when user expands it */
        ev.preventDefault();
        const acc = this.state.account_data[accountName];
        if (!acc) return;

        if (acc._lines_loaded) {
            acc._expanded = !acc._expanded;
            return;
        }

        acc._loading = true;
        try {
            const lines = await this.orm.call(
                "bank.book.report", "get_account_lines",
                [acc.account_id, this.state.selected_partner || [],
                 this.state.date_range || null,
                 this.state.selected_account_list || [],
                 this.state.options || null]
            );
            acc._lines = lines;
            acc._lines_loaded = true;
            acc._expanded = true;
        } catch (e) {
            console.error('Failed to load lines for', accountName, e);
        } finally {
            acc._loading = false;
        }
    }
    gotoJournalEntry(ev) {
        /**
         * Navigates to the journal entry form view based on the selected event target.
         *
         * @param {Event} ev - The event object triggered by the action.
         * @returns {Promise} - A promise that resolves to the result of the action.
         */
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: 'account.move',
            res_id: parseInt(ev.target.attributes["data-id"].value, 10),
            views: [[false, "form"]],
            target: "current",
        });
    }
    getDomain() {
        return [];
    }
    async printPdf(ev) {
        /**
         * Generates and displays a PDF report for the bank book.
         *
         * @param {Event} ev - The event object triggered by the action.
         * @returns {Promise} - A promise that resolves to the result of the action.
         */
        ev.preventDefault();
        var self = this;
        let totals = {
            'total_debit':this.state.total_debit,
            'total_debit_display':this.state.total_debit_display,
            'total_credit':this.state.total_credit,
            'total_credit_display':this.state.total_credit_display,
            'currency':this.state.currency,
        }
        var action_title = self.props.action.display_name;
        // Lines are only lazy-loaded for a single account when its row is
        // expanded (expandAccount/get_account_lines) - state.data/state.total
        // were declared but never populated, so the PDF always had zero
        // account totals AND zero transaction detail. The account_totals
        // (small) and filters travel here; the server fetches the lines
        // itself in IrActionsReportBankBook._get_report_values.
        const account_totals = self.state.account_data || {};
        const account_ids = Object.values(account_totals)
            .map(acc => acc.account_id)
            .filter(id => id != null);
        return self.action.doAction({
            'type': 'ir.actions.report',
            'report_type': 'qweb-pdf',
            'report_name': 'dynamic_accounts_report.bank_book',
            'report_file': 'dynamic_accounts_report.bank_book',
            'data': {
                'move_lines': self.state.move_line,
                'filters': this.filter(),
                'grand_total': totals,
                'account_totals': account_totals,
                'account_ids': account_ids,
                'total': account_totals,
                'title': action_title,
                'report_name': self.props.action.display_name,
                'partner_id': self.state.selected_partner || [],
                'data_range': self.state.date_range || null,
                'account_list': self.state.selected_account_list || [],
                'options': self.state.options || null,
            },
            'display_name': self.props.action.display_name,
        });
    }
    filter() {
    var self=this;
    let startDate, endDate;
    let startYear, startMonth, startDay, endYear, endMonth, endDay;
        if (self.state.date_range){
            const today = new Date();
            if (self.state.date_range === 'year') {
                startDate = new Date(today.getFullYear(), 0, 1);
                endDate = new Date(today.getFullYear(), 11, 31);
            } else if (self.state.date_range === 'quarter') {
                const currentQuarter = Math.floor(today.getMonth() / 3);
                startDate = new Date(today.getFullYear(), currentQuarter * 3, 1);
                endDate = new Date(today.getFullYear(), (currentQuarter + 1) * 3, 0);
            } else if (self.state.date_range === 'month') {
                startDate = new Date(today.getFullYear(), today.getMonth(), 1);
                endDate = new Date(today.getFullYear(), today.getMonth() + 1, 0);
            } else if (self.state.date_range === 'last-month') {
                startDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);
                endDate = new Date(today.getFullYear(), today.getMonth(), 0);
            } else if (self.state.date_range === 'last-year') {
                startDate = new Date(today.getFullYear() - 1, 0, 1);
                endDate = new Date(today.getFullYear() - 1, 11, 31);
            } else if (self.state.date_range === 'last-quarter') {
                const lastQuarter = Math.floor((today.getMonth() - 3) / 3);
                startDate = new Date(today.getFullYear(), lastQuarter * 3, 1);
                endDate = new Date(today.getFullYear(), (lastQuarter + 1) * 3, 0);
            }
            else{
                 startDate = new Date(self.state.date_range.start_date);
                 endDate = new Date(self.state.date_range.end_date);
            }
        // Get the date components for start and end dates
        if (startDate) {
        startYear = startDate.getFullYear();
        startMonth = startDate.getMonth() + 1;
        startDay = startDate.getDate();
        }
        if (endDate) {
        endYear = endDate.getFullYear();
        endMonth = endDate.getMonth() + 1;
        endDay = endDate.getDate();
        }
        }
        const selectedAccountIDs = Object.values(self.state.selected_account_list);
        const selectedAccountNames = selectedAccountIDs.map((accountID) => {
            const matchingAccount = Object.values(self.state.accounts).find(account => account.id === accountID);
            return matchingAccount ? matchingAccount.display_name : '';
        });
        let filters = {
            'partner': self.state.selected_partner_rec,
            'account': selectedAccountNames,
            'options': self.state.options,
            'start_date': null,
            'end_date': null,
        };
        // Check if start and end dates are available before adding them to the filters object
        if (startYear !== undefined && startMonth !== undefined && startDay !== undefined &&
            endYear !== undefined && endMonth !== undefined && endDay !== undefined) {
            filters['start_date'] = `${startYear}-${startMonth < 10 ? '0' : ''}${startMonth}-${startDay < 10 ? '0' : ''}${startDay}`;
            filters['end_date'] = `${endYear}-${endMonth < 10 ? '0' : ''}${endMonth}-${endDay < 10 ? '0' : ''}${endDay}`;
        }
        return filters
    }
    async print_xlsx() {
        /**
         * Generates and downloads an XLSX report for the bank book.
         */
        var self = this;
        var action_title = self.props.action.display_name;
        let totals = {
            'total_debit':this.state.total_debit,
            'total_debit_display':this.state.total_debit_display,
            'total_credit':this.state.total_credit,
            'total_credit_display':this.state.total_credit_display,
            'currency':this.state.currency,
        }
        // Same issue as printPdf(): state.data/state.total were declared
        // but never populated. The xlsx report now fetches lines itself
        // server-side (get_xlsx_report -> get_export_lines) from just the
        // account totals/ids and filters below.
        const account_totals = self.state.account_data || {};
        const account_ids = Object.values(account_totals)
            .map(acc => acc.account_id)
            .filter(id => id != null);
        var datas = {
            'move_lines': self.state.move_line,
            'accounts': self.state.move_line,
            'account_totals': account_totals,
            'account_ids': account_ids,
            'title': action_title,
            'filters': this.filter(),
            'grand_total': totals,
            'partner_id': self.state.selected_partner || [],
            'data_range': self.state.date_range || null,
            'account_list': self.state.selected_account_list || [],
            'options': self.state.options || null,
        }
        var action = {
            'data': {
                'model': 'bank.book.report',
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
    async applyFilter(val, ev, is_delete = false) {
        /**
         * Applies filters to the bank book report based on the provided values.
         *
         * @param {any} val - The value of the filter.
         * @param {Event} ev - The event object triggered by the action.
         * @param {boolean} is_delete - Indicates whether the filter value is being deleted.
         * @returns {void}
         */
        let move_line_list = []
        let move_line_value = []
        let move_line_totals = ''
        this.state.move_line = null
        this.state.data = null
        this.state.total = null
        this.state.filter_applied = true;
        let totalDebitSum = 0;
        let totalCreditSum = 0;
        if (ev) {
            if (ev.input && ev.input.attributes.placeholder.value == 'Partner' && !is_delete) {
                this.state.selected_partner.push(val[0].id)
                this.state.selected_partner_rec.push(val[0])
            } else if (is_delete) {
                let index = this.state.selected_partner_rec.indexOf(val)
                this.state.selected_partner_rec.splice(index, 1)
                this.state.selected_partner = this.state.selected_partner_rec.map((rec) => rec.id)
            }
        }
        else {
            if (val.target.name === 'start_date') {
                this.state.date_range = {
                    ...this.state.date_range,
                    start_date: val.target.value
                };
            } else if (val.target.name === 'end_date') {
                this.state.date_range = {
                    ...this.state.date_range,
                    end_date: val.target.value
                };
            } else if (val.target.attributes["data-value"].value == 'month') {
                this.state.date_range = val.target.attributes["data-value"].value
            } else if (val.target.attributes["data-value"].value == 'year') {
                this.state.date_range = val.target.attributes["data-value"].value
            } else if (val.target.attributes["data-value"].value == 'quarter') {
                this.state.date_range = val.target.attributes["data-value"].value
            } else if (val.target.attributes["data-value"].value == 'last-month') {
                this.state.date_range = val.target.attributes["data-value"].value
            } else if (val.target.attributes["data-value"].value == 'last-year') {
                this.state.date_range = val.target.attributes["data-value"].value
            } else if (val.target.attributes["data-value"].value == 'last-quarter') {
                this.state.date_range = val.target.attributes["data-value"].value
            } else if (val.target.attributes["data-value"].value === 'draft') {
                if (val.target.classList.contains("selected-filter")) {
                    const { draft, ...updatedAccount } = this.state.options;
                    this.state.options = updatedAccount;
                    val.target.classList.remove("selected-filter");
                } else {
                    this.state.options = {
                        ...this.state.options,
                        'draft': true
                    };
                    val.target.classList.add("selected-filter");
                }
            } else if (val.target.attributes["data-value"].value == 'account') {
                if (!val.target.classList.contains("selected-filter")) {
                    this.state.selected_account_list.push(parseInt(val.target.attributes["data-id"].value, 10))
                    val.target.classList.add("selected-filter");
                } else {
                    const updatedList = this.state.selected_account_list.filter(item => item !== parseInt(val.target.attributes["data-id"].value, 10));
                    this.state.selected_account_list = updatedList
                    val.target.classList.remove("selected-filter");
                }
            }
        }
        let filtered_data = await this.orm.call("bank.book.report", "get_filter_values", [this.state.selected_partner, this.state.date_range, this.state.selected_account_list, this.state.options,]);
        this._processAccountData(filtered_data);
        if (this.unfoldButton.el.classList.contains("selected-filter")) {
              this.unfoldButton.el.classList.remove("selected-filter");
        }
    }
    async unfoldAll(ev) {
        /**
         * Unfolds all items in the table body if the event target does not have the 'selected-filter' class,
         * or folds all items if the event target has the 'selected-filter' class.
         *
         * @param {Event} ev - The event object triggered by the action.
         */
        if (!ev.target.classList.contains("selected-filter")) {
            for (var length = 0; length < this.tbody.el.children.length; length++) {
                this.tbody.el.children[length].classList.add('show')
            }
            ev.target.classList.add("selected-filter");
        } else {
            for (var length = 0; length < this.tbody.el.children.length; length++) {
                this.tbody.el.children[length].classList.remove('show')
            }
            ev.target.classList.remove("selected-filter");
        }
    }
    deleteNote(ev) {
        const id = parseInt(ev.target.getAttribute('id'), 10);
        this.state.message_list = this.state.message_list.filter(m => m.id !== id);
    }
}
BankBook.defaultProps = {
    resIds: [],
};
BankBook.template = 'bnk_b_template_new';

BankBook.props = ['*'];
actionRegistry.add("bnk_b", BankBook);
