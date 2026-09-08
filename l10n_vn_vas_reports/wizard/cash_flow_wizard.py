# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""Báo cáo lưu chuyển tiền tệ, phương pháp trực tiếp (mẫu B03-DN)."""

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.services.general_ledger_service import CashFlowService


class VnCashFlowWizard(models.TransientModel):
    _name = 'vn.cash.flow.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'Cash Flow Statement'

    mapping_id = fields.Many2one(
        'vn.report.mapping', string='Mapping',
        domain=[('report_type', '=', 'cash_flow')],
        help='Leave empty for the TT200 direct-method form shipped with the '
             'module.')

    def _service(self):
        return CashFlowService(self.env)

    def _build_report(self):
        self.ensure_one()
        if not self.date_from:
            raise UserError(_(
                "A cash flow statement covers a period, so a start date is "
                "required."))
        result = self._service().generate(
            self._ledger_filter(),
            mapping_code=(self.mapping_id or self._default_mapping()).code)
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data

    def _filter_summary_fields(self):
        return ('target_move', 'journal_ids')

    def _template_values(self, report):
        """Tell the template which method produced this statement.

        The two methods fail in different ways, so the diagnostics have to be
        worded differently: a direct statement is short because a counterpart
        account went unmapped, an indirect one because an adjustment carries the
        wrong sign. Saying the wrong one sends the accountant looking in the
        wrong place.
        """
        values = super()._template_values(report)
        mapping = self.mapping_id or self._default_mapping()
        values['cash_flow_method'] = mapping.cash_flow_method or 'direct'
        return values

    def _default_mapping(self):
        """The mapping for this company's circular, not a hardcoded name."""
        self.ensure_one()
        return self.env['vn.report.mapping'].default_for(
            'cash_flow', self.company_id)

    def _report_title(self):
        return _('Cash Flow Statement')

    def _report_form_code(self):
        return 'B03-DN'

    def _report_form_title(self):
        return 'BÁO CÁO LƯU CHUYỂN TIỀN TỆ (Theo phương pháp trực tiếp)'

    def _screen_template(self):
        return 'l10n_vn_vas_reports.cash_flow_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_vas_reports.action_report_cash_flow'
