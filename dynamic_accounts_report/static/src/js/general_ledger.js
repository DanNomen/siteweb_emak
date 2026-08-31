/** @odoo-module */
const { Component } = owl;
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useRef, useState } from "@odoo/owl";
import { BlockUI } from "@web/core/ui/block_ui";
import { download } from "@web/core/network/download";
const actionRegistry = registry.category("actions");

class GeneralLedger extends owl.Component {
    setup() {
        super.setup(...arguments);
        this.initial_render = true;
        this.orm = useService('orm');
        this.action = useService('action');
        this.tbody = useRef('tbody');
        this.unfoldButton = useRef('unfoldButton');
        this.state = useState({
            account: null,
            account_data: null,
            account_data_list: null,
            account_total: null,
            total_debit: null,
            total_debit_display : null,
            total_credit_display : null,
            total_credit: null,
            currency: null,
            journals: null,
            selected_journal_list: [],
            analytics: null,
            selected_analytic_list: [],
            title: null,
            filter_applied: null,
            account_list: null,
            account_total_list: null,
            date_range: null,
            date_label: null,
            options: null,
            method: {
                        'accural': true
                    },
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
        var self = this;
        var action_title = self.props.action.display_name;
        try {
            // Only fetch account totals (fast read_group query), NO line details
            const data = await this.orm.call(
                "account.general.ledger", "view_report", [self.wizard_id, action_title]
            );
            self._processAccountData(data);
            self.state.title = action_title;
        } catch (el) {
            console.error('GeneralLedger load_data error:', el);
        }
    }

    _processAccountData(data) {
        /** Shared helper to process account data for both load_data and applyFilter */
        const account_totals = data['account_totals'] || {};
        let totalDebitSum = 0;
        let totalCreditSum = 0;
        let currency = null;

        Object.values(account_totals).forEach(acc => {
            currency = acc.currency_id || currency;
            totalDebitSum += acc.total_debit || 0;
            acc.total_debit_display = this.formatNumberWithSeparators(acc.total_debit || 0);
            totalCreditSum += acc.total_credit || 0;
            acc.total_credit_display = this.formatNumberWithSeparators(acc.total_credit || 0);
            acc.balance_display = this.formatNumberWithSeparators((acc.total_debit || 0) - (acc.total_credit || 0));
            acc._lines_loaded = false; // lazy load flag
            acc._lines = [];          // will be populated on expand
        });

        const account_list = Object.keys(account_totals);
        this.state.account = account_list;
        this.state.account_list = account_list;
        this.state.account_data = data;
        this.state.account_data_list = data;
        this.state.account_total = account_totals;
        this.state.account_total_list = account_totals;
        if (data['journal_ids']) { this.state.journals = data['journal_ids']; }
        if (data['analytic_ids']) { this.state.analytics = data['analytic_ids']; }
        if (currency) { this.state.currency = currency; }
        this.state.total_debit = totalDebitSum.toFixed(2);
        this.state.total_debit_display = this.formatNumberWithSeparators(totalDebitSum);
        this.state.total_credit = totalCreditSum.toFixed(2);
        this.state.total_credit_display = this.formatNumberWithSeparators(totalCreditSum);
    }

    async expandAccount(ev, accountName) {
        /** Lazy-load move lines for a single account when user expands it */
        ev.preventDefault();
        const acc = this.state.account_total[accountName];
        if (!acc) return;

        // Toggle collapse if already loaded
        if (acc._lines_loaded) {
            acc._expanded = !acc._expanded;
            return;
        }

        acc._loading = true;
        try {
            const lines = await this.orm.call(
                "account.general.ledger", "get_account_lines",
                [acc.account_id,
                 this.state.selected_journal_list || [],
                 this.state.date_range || null,
                 this.state.options || null,
                 this.state.selected_analytic_list || [],
                 this.state.method || null]
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
    async printPdf(ev) {
        ev.preventDefault();
        var self = this;
        let totals = {
            'total_debit':this.state.total_debit || false,
            'total_debit_display':this.state.total_debit_display || false,
            'total_credit':this.state.total_credit || false,
            'total_credit_display':this.state.total_credit_display || false,
            'currency':this.state.currency  || false,
        }
        var action_title = self.props.action.display_name;
        // Move-line detail is fetched server-side (see IrActionsReportGeneralLedger
        // ._get_report_values in account_general_ledger.py) instead of being
        // fetched here and shipped through the report action's data payload -
        // for a general ledger with many accounts/entries that payload could
        // exceed the web server's request size limit (413 Request Entity Too
        // Large). Only small filter values and account ids travel from here.
        const account_totals = self.state.account_total || {};
        const account_ids = Object.values(account_totals)
            .map(acc => acc.account_id)
            .filter(id => id != null);
        return self.action.doAction({
            'type': 'ir.actions.report',
            'report_type': 'qweb-pdf',
            'report_name': 'dynamic_accounts_report.general_ledger',
            'report_file': 'dynamic_accounts_report.general_ledger',
            'data': {
                'account': self.state.account,
                'account_ids': account_ids,
                'total': self.state.account_total,
                'title': action_title,
                'filters': this.filter(),
                'grand_total': totals,
                'report_name': self.props.action.display_name,
                'journal_ids': self.state.selected_journal_list || [],
                'date_range': self.state.date_range || null,
                'options': self.state.options || null,
                'analytic_ids': self.state.selected_analytic_list || [],
                'method': self.state.method || null,
            },
            'display_name': self.props.action.display_name,
        });
    }
    async print_xlsx() {
        var self = this;
        let totals = {
            'total_debit':this.state.total_debit,
            'total_debit_display':this.state.total_debit_display || false,
            'total_credit':this.state.total_credit,
            'total_credit_display':this.state.total_credit_display || false,
            'currency':this.state.currency,
        }
        var action_title = self.props.action.display_name;
        // The on-screen report only lazy-loads move lines for a single
        // account when its row is expanded (expandAccount/get_account_lines),
        // so account_data/account_total never hold every account's lines.
        // Rather than fetching them here and shipping them back to the
        // server in this POST body (which, for a general ledger with many
        // accounts/entries, could exceed the web server's request size
        // limit and produce a 413 Request Entity Too Large / corrupted
        // download), get_xlsx_report() now fetches the lines itself
        // server-side from just the account ids and filter values below.
        const account_totals = self.state.account_total || {};
        const account_ids = Object.values(account_totals)
            .map(acc => acc.account_id)
            .filter(id => id != null);
        var datas = {
            'account': self.state.account,
            'account_ids': account_ids,
            'total': self.state.account_total,
            'title': action_title,
            'filters': this.filter(),
            'grand_total': totals,
            'journal_ids': self.state.selected_journal_list || [],
            'date_range': self.state.date_range || null,
            'options': self.state.options || null,
            'analytic_ids': self.state.selected_analytic_list || [],
            'method': self.state.method || null,
        }
        var action = {
            'data': {
                'model': 'account.general.ledger',
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
    gotoJournalEntry(ev) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: 'account.move',
            res_id: parseInt(ev.target.attributes["data-id"].value, 10),
            views: [[false, "form"]],
            target: "current",
        });
    }
    gotoJournalItem(ev) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: 'account.move.line',
            name: "Journal Items",
            views: [[false, "list"]],
            domain: [["account_id", "=", parseInt(ev.target.attributes["data-id"].value, 10)]],
            target: "current",
        });
    }
    getDomain() {
        return [];
    }
    async applyFilter(val, ev, is_delete = false) {
        let account_list = []
        let account_totals = ''
        let totalDebitSum = 0;
        let totalCreditSum = 0;
        this.state.account = null
        this.state.account_data = null
        this.state.account_total = null
        this.state.filter_applied = true;
        if (ev) {
            if (ev.input && ev.input.attributes.placeholder.value == 'Account' && !is_delete) {
                this.state.selected_analytic.push(val[0].id)
                this.state.selected_analytic_account_rec.push(val[0])
            } else if (is_delete) {
                let index = this.state.selected_analytic_account_rec.indexOf(val)
                this.state.selected_analytic_account_rec.splice(index, 1)
                this.state.selected_analytic = this.state.selected_analytic_account_rec.map((rec) => rec.id)
            }
        }
        else {
            if (val.target.name === 'start_date') {
                this.state.date_range = {
                    ...this.state.date_range,
                    start_date: val.target.value
                };
                this.state.date_label = null; // will be rebuilt below
            } else if (val.target.name === 'end_date') {
                this.state.date_range = {
                    ...this.state.date_range,
                    end_date: val.target.value
                };
                this.state.date_label = null; // will be rebuilt below
            } else if (val.target.attributes["data-value"].value == 'month') {
                this.state.date_range = val.target.attributes["data-value"].value;
                this.state.date_label = 'Ce mois';
            } else if (val.target.attributes["data-value"].value == 'year') {
                this.state.date_range = val.target.attributes["data-value"].value;
                this.state.date_label = 'Cette année';
            } else if (val.target.attributes["data-value"].value == 'quarter') {
                this.state.date_range = val.target.attributes["data-value"].value;
                this.state.date_label = 'Ce trimestre';
            } else if (val.target.attributes["data-value"].value == 'last-month') {
                this.state.date_range = val.target.attributes["data-value"].value;
                this.state.date_label = 'Mois dernier';
            } else if (val.target.attributes["data-value"].value == 'last-year') {
                this.state.date_range = val.target.attributes["data-value"].value;
                this.state.date_label = 'Année dernière';
            } else if (val.target.attributes["data-value"].value == 'last-quarter') {
                this.state.date_range = val.target.attributes["data-value"].value;
                this.state.date_label = 'Trimestre dernier';
            }
            else if (val.target.attributes["data-value"].value == 'journal') {
                if (!val.target.classList.contains("selected-filter")) {
                    this.state.selected_journal_list.push(parseInt(val.target.attributes["data-id"].value, 10))
                    val.target.classList.add("selected-filter");
                } else {
                    const updatedList = this.state.selected_journal_list.filter(item => item !== parseInt(val.target.attributes["data-id"].value, 10));
                    this.state.selected_journal_list = updatedList
                    val.target.classList.remove("selected-filter");
                }
            }

            else if (val.target.attributes["data-value"].value == 'analytic') {
                if (!val.target.classList.contains("selected-filter")) {
                    this.state.selected_analytic_list.push(parseInt(val.target.attributes["data-id"].value, 10))
                    val.target.classList.add("selected-filter");
                } else {
                    const updatedList = this.state.selected_analytic_list.filter(item => item !== parseInt(val.target.attributes["data-id"].value, 10));
                    this.state.selected_analytic_list = updatedList
                    val.target.classList.remove("selected-filter");
                }
            }
            else if (val.target.attributes["data-value"].value == 'journal') {

                if (!val.target.classList.contains("selected-filter")) {
                    this.state.selected_journal_list.push(parseInt(val.target.attributes["data-id"].value, 10))
                    val.target.classList.add("selected-filter");
                } else {
                    const updatedList = this.state.selected_journal_list.filter(item => item !== parseInt(val.target.attributes["data-id"].value, 10));
                    this.state.selected_journal_list = updatedList
                    val.target.classList.remove("selected-filter");
                }
            }
            else if (val.target.attributes["data-value"].value == 'analytic') {
                if (!val.target.classList.contains("selected-filter")) {
                    this.state.selected_analytic_list.push(parseInt(val.target.attributes["data-id"].value, 10))
                    val.target.classList.add("selected-filter");
                } else {
                    const updatedList = this.state.selected_analytic_list.filter(item => item !== parseInt(val.target.attributes["data-id"].value, 10));
                    this.state.selected_analytic_list = updatedList
                    val.target.classList.remove("selected-filter");
                }
            }
            else if (val.target.attributes["data-value"].value === 'draft') {
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
            }else if (val.target.attributes["data-value"].value === 'cash-basis') {
                if (val.target.classList.contains("selected-filter")) {
                    const { cash, ...updatedAccount } = this.state.method;
                    this.state.method = updatedAccount;
                    this.state.method = {
                        ...this.state.method,
                        'accrual': true
                    }
                    val.target.classList.remove("selected-filter");
                } else {
                    const { accrual, ...updatedAccount } = this.state.method;
                    this.state.method = updatedAccount;
                    this.state.method = {
                        ...this.state.method,
                        'cash': true
                    };
                    val.target.classList.add("selected-filter");
                }
            }
        }
        let filtered_data = await this.orm.call("account.general.ledger", "get_filter_values", [this.state.selected_journal_list, this.state.date_range, this.state.options, this.state.selected_analytic_list,this.state.method]);
        // Ensure account_totals always exists even if no data returned
        if (!filtered_data['account_totals']) {
            filtered_data['account_totals'] = {};
        }
        let currency = null;
        for (let index in filtered_data) {
            const value = filtered_data[index];
            if (index === 'account_totals') {
                // get_filter_values() only ever returns 'account_totals',
                // 'journal_ids' and 'analytic_ids' - there is no other key,
                // so building account_list from "any other key" (as before)
                // always left it empty after a filter, which in turn made
                // the XLSX/PDF export's account loop see zero accounts
                // ("no data") even though the on-screen table (which reads
                // account_data.account_totals directly) still had rows.
                account_totals = value;
                account_list = Object.keys(account_totals);
                Object.values(account_totals).forEach(acc => {
                    currency = acc.currency_id;
                    totalDebitSum += acc.total_debit || 0;
                    acc.total_debit_display = this.formatNumberWithSeparators(acc.total_debit || 0);
                    totalCreditSum += acc.total_credit || 0;
                    acc.total_credit_display = this.formatNumberWithSeparators(acc.total_credit || 0);
                    acc.balance_display = this.formatNumberWithSeparators((acc.total_debit || 0) - (acc.total_credit || 0));
                });
            } else if (index === 'journal_ids') {
                this.state.journals = value;
            } else if (index === 'analytic_ids') {
                this.state.analytics = value;
            }
        }
        this.state.account = account_list;
        this.state.account_data = filtered_data;
        this.state.account_total = account_totals;
        if (currency) { this.state.currency = currency; }
        this.state.total_debit = totalDebitSum.toFixed(2);
        this.state.total_debit_display = this.formatNumberWithSeparators(totalDebitSum);
        this.state.total_credit = totalCreditSum.toFixed(2);
        this.state.total_credit_display = this.formatNumberWithSeparators(totalCreditSum);
        if (this.unfoldButton.el.classList.contains("selected-filter")) {
            this.unfoldButton.el.classList.remove("selected-filter");
        }
    }
    async unfoldAll(ev) {
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
        const selectedJournalIDs = Object.values(self.state.selected_journal_list);
        const selectedJournalNames = selectedJournalIDs.map((journalID) => {
          const journal = self.state.journals.find((journal) => journal.id === journalID);
          return journal ? journal.name : '';
        });
        const selectedAnalyticIDs = Object.values(self.state.selected_analytic_list);
        const selectedAnalyticNames = selectedAnalyticIDs.map((analyticID) => {
          const analytic = self.state.analytics.find((analytic) => analytic.id === analyticID);
          return analytic ? analytic.name : '';
        });
        let filters = {
            'journal': selectedJournalNames,
            'analytic': selectedAnalyticNames,
            'account': self.state.selected_analytic_account_rec,
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
}
GeneralLedger.props = {
    action: { type: Object },
    actionStack: { type: Array, optional: true },
    '*': true,
};
GeneralLedger.defaultProps = { resIds: [] };
GeneralLedger.template = 'gl_template_new';
actionRegistry.add("gen_l", GeneralLedger);
