/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class DashboardDirection extends Component {
    static template = "dashboard_direction.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.state = useState({ kpis: null, loading: true });

        onWillStart(async () => {
            this.state.kpis = await this.orm.call(
                "dashboard.direction",
                "get_all_kpis",
                []
            );
            this.state.loading = false;
        });
    }

    formatMoney(value) {
        if (value === undefined || value === null) return "-";
        const symbol = this.state.kpis?.currency_symbol || "";
        return `${Math.round(value).toLocaleString("fr-FR")} ${symbol}`;
    }

    evolutionClass(pct) {
        if (pct === undefined || pct === null) return "";
        return pct >= 0 ? "text-success" : "text-danger";
    }
}

registry.category("actions").add("dashboard_direction.main", DashboardDirection);
