/** @odoo-module **/
/* Target: Odoo 18.0 Community Edition
 *
 * Interactive viewer for the Vietnamese accounting books, as an OWL client
 * action (the legacy AbstractAction stack the 14.0 branch uses is gone).
 *
 * The component never computes a figure. It fetches HTML the server rendered
 * from the same QWeb template the PDF uses, then adds collapsing, filtering
 * and drill-down on top — all plain DOM work on the injected markup, because
 * the markup is the report and OWL has nothing to own inside it.
 */

import { Component, markup, onMounted, onPatched, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class VnReportViewer extends Component {
    static template = "l10n_vn_vas_reports.ReportViewer";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.ui = useService("ui");

        const context = (this.props.action && this.props.action.context) || {};
        this.wizardModel = context.vn_report_model;
        this.wizardId = context.vn_report_wizard_id;
        this.reportName = (this.props.action && this.props.action.name) || _t("Report");

        this.state = useState({
            html: markup(""),
            failed: false,
            summary: "",
            filtering: false,
        });
        // Keyed by the stable group key the template stamps onto each block
        // (account code, partner or product id) — the positional "g0" key is
        // a different account after a refresh with another period.
        this.collapsed = {};
        this.searchQuery = "";
        this.contentRef = useRef("content");
        this.searchRef = useRef("search");

        onWillStart(() => this._fetchReport());
        onMounted(() => this._afterRender());
        onPatched(() => this._afterRender());
    }

    // ------------------------------------------------------------------
    // Data
    // ------------------------------------------------------------------

    /** The wizard is a TransientModel: when it has been vacuumed the RPC
     *  fails and the viewer shows a recoverable empty state, not a crash. */
    async _fetchReport() {
        if (!this.wizardModel || !this.wizardId) {
            this.state.failed = true;
            return;
        }
        try {
            const html = await this.orm.call(
                this.wizardModel, "get_report_html", [[this.wizardId]]);
            this.state.html = markup(html || "");
            this.state.failed = false;
        } catch {
            this.state.html = markup("");
            this.state.failed = true;
        }
    }

    // ------------------------------------------------------------------
    // DOM work on the injected report
    // ------------------------------------------------------------------

    _afterRender() {
        this._applySearch();
        this._applyCollapsed();
        this._updateSummary();
    }

    _groupKey(row) {
        const key = row.getAttribute("data-group-key");
        return key === null || key === "" ? row.dataset.group : key;
    }

    _rows(selector) {
        return this.contentRef.el
            ? [...this.contentRef.el.querySelectorAll(selector)] : [];
    }

    _applyCollapsed() {
        for (const row of this._rows(".o_vn_group_row")) {
            const collapsed = Boolean(this.collapsed[this._groupKey(row)]);
            row.classList.toggle("o_vn_collapsed", collapsed);
            const caret = row.querySelector(".o_vn_caret");
            if (caret) {
                caret.classList.toggle("fa-caret-right", collapsed);
                caret.classList.toggle("fa-caret-down", !collapsed);
            }
            for (const child of this._rows(
                    `[data-group-child="${row.dataset.group}"]`)) {
                child.classList.toggle("o_vn_hidden", collapsed);
            }
        }
    }

    /** Hide non-matching lines and any group left with nothing to show. The
     *  totals in the table still cover the whole period — the notice says so. */
    _applySearch() {
        const query = this.searchQuery;
        for (const row of this._rows(".o_vn_line")) {
            row.classList.toggle(
                "o_vn_filtered",
                Boolean(query) && !row.textContent.toLowerCase().includes(query));
        }
        for (const row of this._rows(".o_vn_group_row")) {
            const visible = this._rows(
                `.o_vn_line[data-group-child="${row.dataset.group}"]`)
                .filter((line) => !line.classList.contains("o_vn_filtered"));
            row.classList.toggle(
                "o_vn_filtered", Boolean(query) && visible.length === 0);
        }
    }

    _updateSummary() {
        const groups = this._rows(".o_vn_group_row").length;
        const lines = this._rows(".o_vn_line")
            .filter((row) => !row.classList.contains("o_vn_filtered")).length;
        this.state.summary = _t("%s groups, %s lines", groups, lines);
    }

    // ------------------------------------------------------------------
    // Handlers
    // ------------------------------------------------------------------

    /** One delegated handler for everything inside the server markup. */
    onContentClick(ev) {
        const drill = ev.target.closest(".o_vn_drillable");
        if (drill) {
            ev.preventDefault();
            ev.stopPropagation();
            return this._drillDown(drill);
        }
        const toggle = ev.target.closest(".o_vn_group_toggle");
        if (toggle) {
            const key = this._groupKey(toggle);
            this.collapsed[key] = !this.collapsed[key];
            this._applyCollapsed();
            return;
        }
        const line = ev.target.closest(".o_vn_line[data-move-id]");
        if (line) {
            return this._openMove(parseInt(line.getAttribute("data-move-id"), 10));
        }
    }

    async _drillDown(el) {
        const holder = el.closest("[data-line-code]");
        const code = holder && holder.getAttribute("data-line-code");
        if (!code || !this.wizardId) {
            return;
        }
        const action = await this.orm.call(
            this.wizardModel, "action_drill_down", [[this.wizardId], code]);
        return this.actionService.doAction(action);
    }

    _openMove(moveId) {
        if (!moveId) {
            return;
        }
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "account.move",
            res_id: moveId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    onExpandAll() {
        this.collapsed = {};
        this._applyCollapsed();
    }

    onCollapseAll() {
        for (const row of this._rows(".o_vn_group_row")) {
            this.collapsed[this._groupKey(row)] = true;
        }
        this._applyCollapsed();
    }

    /** Built server-side from the same wizard, so the sheet carries the same
     *  period and filters as the screen. */
    async onExportXlsx() {
        await this._wizardAction("action_export_xlsx");
    }

    async onPrintPdf() {
        await this._wizardAction("action_print_pdf");
    }

    async _wizardAction(method) {
        this.ui.block();
        try {
            const action = await this.orm.call(
                this.wizardModel, method, [[this.wizardId]]);
            await this.actionService.doAction(action);
        } finally {
            this.ui.unblock();
        }
    }

    async onRefresh() {
        this.ui.block();
        try {
            await this._fetchReport();
        } finally {
            this.ui.unblock();
        }
    }

    /** Reopen the same wizard record so the period or filters can change. */
    onEditFilters() {
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: this.wizardModel,
            res_id: this.wizardId,
            views: [[false, "form"]],
            target: "new",
        });
    }

    onSearch(ev) {
        this.searchQuery = (ev.target.value || "").trim().toLowerCase();
        this.state.filtering = Boolean(this.searchQuery);
        this._applySearch();
        this._applyCollapsed();
        this._updateSummary();
    }

    onSearchClear() {
        if (this.searchRef.el) {
            this.searchRef.el.value = "";
        }
        this.searchQuery = "";
        this.state.filtering = false;
        this._applySearch();
        this._applyCollapsed();
        this._updateSummary();
    }
}

registry.category("actions").add("vn_report_viewer", VnReportViewer);
