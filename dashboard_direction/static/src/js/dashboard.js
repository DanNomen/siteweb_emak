/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { getColor, hexToRGBA } from "@web/core/colors/colors";
import { cookie } from "@web/core/browser/cookie";
import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";

const MONTH_LABELS = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
];

const KPI_CARDS = [
    { key: "revenue", label: "Chiffre d'affaires", icon: "fa-line-chart" },
    { key: "gross_margin", label: "Marge brute", icon: "fa-percent" },
    { key: "receivables", label: "Créances clients", icon: "fa-users" },
    { key: "treasury", label: "Trésorerie", icon: "fa-university" },
    { key: "stock_value", label: "Valeur en stock", icon: "fa-cubes" },
    { key: "purchases", label: "Achats du mois", icon: "fa-shopping-cart" },
];

export class DashboardDirection extends Component {
    static template = "dashboard_direction.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ kpis: null, loading: true });
        this.colorScheme = cookie.get("color_scheme");
        this.revenueChartRef = useRef("revenueChart");
        this.agingChartRef = useRef("agingChart");
        this.revenueChart = null;
        this.agingChart = null;

        const blueColor = getColor(0, this.colorScheme, "md");
        const peachColor = getColor(6, this.colorScheme, "md");
        const blueTint = hexToRGBA(blueColor, 0.1);
        const peachTint = hexToRGBA(peachColor, 0.14);
        this.cards = KPI_CARDS.map((card, index) => ({
            ...card,
            bg: index % 4 < 2 ? blueTint : peachTint,
            iconColor: index % 4 < 2 ? blueColor : peachColor,
        }));

        const today = new Date();
        const prevMonthDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        this.compareLabel = `vs ${MONTH_LABELS[prevMonthDate.getMonth()].toLowerCase()} ${prevMonthDate.getFullYear()}`;

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            this.state.kpis = await this.orm.call(
                "dashboard.direction",
                "get_all_kpis",
                []
            );
            this.state.loading = false;
        });

        useEffect(
            () => {
                if (!this.state.loading) {
                    this.renderRevenueChart();
                    this.renderAgingChart();
                }
                return () => {
                    this.revenueChart?.destroy();
                    this.agingChart?.destroy();
                };
            },
            () => [this.state.loading]
        );
    }

    renderRevenueChart() {
        const points = this.state.kpis.revenue_evolution;
        const color = getColor(0, this.colorScheme, "md");
        this.revenueChart = new Chart(this.revenueChartRef.el, {
            type: "line",
            data: {
                labels: points.map((p) => `${MONTH_LABELS[p.month - 1]} ${new Date().getFullYear()}`),
                datasets: [
                    {
                        data: points.map((p) => p.value),
                        borderColor: color,
                        backgroundColor: hexToRGBA(color, 0.15),
                        fill: "start",
                        tension: 0.35,
                        borderWidth: 2,
                        pointRadius: 3,
                        pointBackgroundColor: color,
                        pointBorderColor: "#fff",
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { intersect: false, mode: "index" },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: "#eef0f2" },
                        ticks: { callback: (v) => this.formatMoney(v) },
                    },
                    x: { grid: { display: false } },
                },
            },
        });
    }

    renderAgingChart() {
        const buckets = this.state.kpis.receivables_aging;
        const bucketKeys = ["0_30", "31_60", "61_90", "90_plus"];
        const labels = ["0-30j", "31-60j", "61-90j", "90j+"];
        const values = bucketKeys.map((k) => buckets[k]);
        const colors = [0, 6, 2, 5].map((i) => getColor(i, this.colorScheme, "md"));
        this.agingChart = new Chart(this.agingChartRef.el, {
            type: "doughnut",
            data: {
                labels,
                datasets: [
                    {
                        data: values,
                        backgroundColor: colors,
                        borderColor: "#fff",
                        borderWidth: 2,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                cutout: "65%",
                onClick: (evt, elements) => {
                    if (elements.length) {
                        this.openAgingAction(bucketKeys[elements[0].index]);
                    }
                },
                onHover: (evt, elements) => {
                    evt.native.target.style.cursor = elements.length ? "pointer" : "default";
                },
                plugins: { legend: { position: "bottom", labels: { boxWidth: 10, color: "#8a8a8a" } } },
            },
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

    evolutionIcon(pct) {
        if (pct === undefined || pct === null) return "";
        return pct >= 0 ? "fa-long-arrow-up" : "fa-long-arrow-down";
    }

    /**
     * Ouvre le détail (liste + fiches) correspondant à un KPI, à partir de
     * la définition d'action renvoyée par le serveur (mêmes filtres que
     * ceux utilisés pour calculer la valeur affichée).
     */
    openAction(actionDef) {
        if (!actionDef) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: actionDef.res_model,
            domain: actionDef.domain,
            name: actionDef.name,
            views: actionDef.view_mode.split(",").map((mode) => [false, mode]),
            target: "current",
        });
    }

    openKpiDetail(key) {
        this.openAction(this.state.kpis[key]?.action);
    }

    openStockAction(key) {
        this.openAction(this.state.kpis.stock_status.actions?.[key]);
    }

    openAgingAction(key) {
        this.openAction(this.state.kpis.receivables_aging.actions?.[key]);
    }

    openProduct(productId) {
        if (!productId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.product",
            res_id: productId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("dashboard_direction.main", DashboardDirection);
