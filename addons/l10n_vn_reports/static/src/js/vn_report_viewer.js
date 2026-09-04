odoo.define('l10n_vn_reports.ReportViewer', function (require) {
'use strict';

/**
 * Interactive viewer for the Vietnamese accounting books.
 *
 * Built on the legacy widget stack rather than OWL on purpose: Odoo 14 ships
 * OWL 1.x, where the hook and lifecycle API differs from both 13 and 16, while
 * `AbstractAction` is stable across 13–16. For a report surface that is mostly
 * server-rendered HTML plus a handful of DOM interactions, the legacy widget is
 * the lower-risk choice and the one that will survive a 14→16 migration with
 * fewer edits.
 *
 * The widget never computes a figure. It fetches HTML the server rendered from
 * the same QWeb template the PDF uses, then adds collapsing, filtering and
 * drill-down on top.
 */

const AbstractAction = require('web.AbstractAction');
const core = require('web.core');
const framework = require('web.framework');

const _t = core._t;

const VnReportViewer = AbstractAction.extend({
    template: 'l10n_vn_reports.ReportViewer',

    events: {
        'click .o_vn_group_toggle': '_onToggleGroup',
        'click .o_vn_expand_all': '_onExpandAll',
        'click .o_vn_collapse_all': '_onCollapseAll',
        'click .o_vn_print_pdf': '_onPrintPdf',
        'click .o_vn_export_xlsx': '_onExportXlsx',
        'click .o_vn_refresh': '_onRefresh',
        'click .o_vn_edit_filters': '_onEditFilters',
        'click .o_vn_line[data-move-id]': '_onOpenMove',
        'click .o_vn_drillable': '_onDrillDown',
        'input .o_vn_search_input': '_onSearch',
        'click .o_vn_search_clear': '_onSearchClear',
    },

    /**
     * @override
     */
    init: function (parent, action) {
        this._super.apply(this, arguments);
        const context = (action && action.context) || {};
        this.wizardModel = context.vn_report_model;
        this.wizardId = context.vn_report_wizard_id;
        this.reportName = (action && action.name) || _t('Report');
        this.reportHtml = '';
        this.loadFailed = false;
        // Keyed by the group index the template stamped onto each block.
        this.collapsedGroups = {};
    },

    /**
     * @override
     */
    willStart: function () {
        return Promise.all([this._super.apply(this, arguments), this._fetchReport()]);
    },

    /**
     * @override
     */
    start: function () {
        const self = this;
        return this._super.apply(this, arguments).then(function () {
            self._renderReport();
        });
    },

    //--------------------------------------------------------------------------
    // Data
    //--------------------------------------------------------------------------

    /**
     * Ask the wizard for server-rendered HTML.
     *
     * The wizard is a TransientModel, so its record is eventually vacuumed. When
     * that has happened the RPC fails and we show a recoverable empty state
     * rather than a traceback.
     *
     * @private
     * @returns {Promise}
     */
    _fetchReport: function () {
        const self = this;
        if (!this.wizardModel || !this.wizardId) {
            this.loadFailed = true;
            return Promise.resolve();
        }
        return this._rpc({
            model: this.wizardModel,
            method: 'get_report_html',
            args: [[this.wizardId]],
        }).then(function (html) {
            self.reportHtml = html || '';
            self.loadFailed = false;
        }).guardedCatch(function () {
            self.reportHtml = '';
            self.loadFailed = true;
        });
    },

    //--------------------------------------------------------------------------
    // Rendering
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _renderReport: function () {
        const $content = this.$('.o_vn_report_content');
        if (this.loadFailed) {
            $content.html(core.qweb.render('l10n_vn_reports.ReportViewerExpired'));
            this.$('.o_vn_toolbar_actions').addClass('o_vn_hidden');
            return;
        }
        $content.html(this.reportHtml);
        this.$('.o_vn_toolbar_actions').removeClass('o_vn_hidden');
        this._applyCollapsed();
        this._updateSummary();
    },

    /**
     * Apply the collapsed state to every group block.
     *
     * @private
     */
    /**
     * The stable identity of a group, used to remember its collapsed state.
     *
     * The positional key ("g0", "g1") is what ties a header row to its child
     * rows in the DOM, but it is useless for remembering anything: after a
     * refresh with a different period, group 0 is a different account. So the
     * template also emits the account code, partner or product id, and the
     * collapsed state is keyed on that instead.
     *
     * @private
     */
    _groupKey: function ($row) {
        const key = $row.attr('data-group-key');
        return key === undefined || key === '' ? $row.data('group') : key;
    },

    _applyCollapsed: function () {
        const self = this;
        this.$('.o_vn_group_row').each(function () {
            const $row = $(this);
            const group = $row.data('group');
            const collapsed = Boolean(self.collapsedGroups[self._groupKey($row)]);
            $row.toggleClass('o_vn_collapsed', collapsed);
            $row.find('.o_vn_caret')
                .toggleClass('fa-caret-right', collapsed)
                .toggleClass('fa-caret-down', !collapsed);
            self.$('[data-group-child="' + group + '"]')
                .toggleClass('o_vn_hidden', collapsed);
        });
    },

    /**
     * Show how much is on screen. Deliberately worded as a count of what is
     * displayed, because the totals in the table always cover the whole period.
     *
     * @private
     */
    _updateSummary: function () {
        const groups = this.$('.o_vn_group_row').length;
        const lines = this.$('.o_vn_line').not('.o_vn_filtered').length;
        this.$('.o_vn_summary').text(
            _.str.sprintf(_t('%s groups, %s lines'), groups, lines));
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onToggleGroup: function (ev) {
        const key = this._groupKey($(ev.currentTarget));
        this.collapsedGroups[key] = !this.collapsedGroups[key];
        this._applyCollapsed();
    },

    /**
     * @private
     */
    _onExpandAll: function () {
        this.collapsedGroups = {};
        this._applyCollapsed();
    },

    /**
     * @private
     */
    _onCollapseAll: function () {
        const self = this;
        this.$('.o_vn_group_row').each(function () {
            self.collapsedGroups[self._groupKey($(this))] = true;
        });
        this._applyCollapsed();
    },

    /**
     * Open the ledger behind one item of a financial statement.
     *
     * Only the item code travels to the server. Which accounts make up an item
     * is mapping data and the server already knows it; pushing a list of
     * account ids through the DOM would put a second copy of that knowledge
     * somewhere it can go stale.
     *
     * @private
     */
    _onDrillDown: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const code = $(ev.currentTarget).closest('[data-line-code]')
            .attr('data-line-code');
        if (!code || !this.wizardId) {
            return;
        }
        const self = this;
        return this._rpc({
            model: this.wizardModel,
            method: 'action_drill_down',
            args: [[this.wizardId], code],
        }).then(function (action) {
            return self.do_action(action);
        });
    },

    /**
     * Open the journal entry behind a ledger line.
     *
     * @private
     */
    _onOpenMove: function (ev) {
        const moveId = parseInt($(ev.currentTarget).attr('data-move-id'), 10);
        if (!moveId) {
            return;
        }
        this.do_action({
            type: 'ir.actions.act_window',
            res_model: 'account.move',
            res_id: moveId,
            views: [[false, 'form']],
            target: 'current',
        });
    },

    /**
     * @private
     * @returns {Promise}
     */
    /**
     * Export the report on screen to a workbook.
     *
     * Built server-side from the same wizard, so the sheet carries the same
     * period and filters as the screen. Rebuilding it from the rendered HTML
     * would give a file that agrees with the table only until someone collapses
     * a group or types in the search box.
     *
     * @private
     */
    _onExportXlsx: function () {
        const self = this;
        framework.blockUI();
        return this._rpc({
            model: this.wizardModel,
            method: 'action_export_xlsx',
            args: [[this.wizardId]],
        }).then(function (action) {
            framework.unblockUI();
            return self.do_action(action);
        }).guardedCatch(function () {
            framework.unblockUI();
        });
    },

    _onPrintPdf: function () {
        const self = this;
        framework.blockUI();
        return this._rpc({
            model: this.wizardModel,
            method: 'action_print_pdf',
            args: [[this.wizardId]],
        }).then(function (action) {
            framework.unblockUI();
            return self.do_action(action);
        }).guardedCatch(function () {
            framework.unblockUI();
        });
    },

    /**
     * @private
     * @returns {Promise}
     */
    _onRefresh: function () {
        const self = this;
        framework.blockUI();
        return this._fetchReport().then(function () {
            framework.unblockUI();
            self._renderReport();
        });
    },

    /**
     * Reopen the same wizard record so the period or filters can be changed.
     *
     * @private
     */
    _onEditFilters: function () {
        this.do_action({
            type: 'ir.actions.act_window',
            res_model: this.wizardModel,
            res_id: this.wizardId,
            views: [[false, 'form']],
            target: 'new',
        });
    },

    /**
     * Hide non-matching lines, and any group left with nothing to show.
     *
     * This filters the rendered rows only; the totals still cover the whole
     * period, which is why the notice below the toolbar says so rather than
     * leaving the user to guess.
     *
     * @private
     */
    _onSearch: function (ev) {
        const query = ($(ev.currentTarget).val() || '').trim().toLowerCase();
        const $notice = this.$('.o_vn_filter_notice');

        if (!query) {
            this.$('.o_vn_line, .o_vn_group_row').removeClass('o_vn_filtered');
            $notice.addClass('o_vn_hidden');
            this._updateSummary();
            return;
        }

        this.$('.o_vn_line').each(function () {
            const $row = $(this);
            const matches = $row.text().toLowerCase().indexOf(query) !== -1;
            $row.toggleClass('o_vn_filtered', !matches);
        });

        const self = this;
        this.$('.o_vn_group_row').each(function () {
            const $row = $(this);
            const group = $row.data('group');
            const visible = self.$('.o_vn_line[data-group-child="' + group + '"]')
                .not('.o_vn_filtered').length;
            $row.toggleClass('o_vn_filtered', visible === 0);
        });

        $notice.removeClass('o_vn_hidden');
        this._updateSummary();
    },

    /**
     * @private
     */
    _onSearchClear: function () {
        this.$('.o_vn_search_input').val('');
        this.$('.o_vn_line, .o_vn_group_row').removeClass('o_vn_filtered');
        this.$('.o_vn_filter_notice').addClass('o_vn_hidden');
        this._updateSummary();
    },
});

core.action_registry.add('vn_report_viewer', VnReportViewer);

return VnReportViewer;

});
