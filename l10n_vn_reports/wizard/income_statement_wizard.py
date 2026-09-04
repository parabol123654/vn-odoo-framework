# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Báo cáo kết quả hoạt động kinh doanh (mẫu B02-DN)."""

from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.services.general_ledger_service import (
    IncomeStatementService,
)


class VnIncomeStatementWizard(models.TransientModel):
    _name = 'vn.income.statement.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'Income Statement Report'

    _report_code = 'income_statement'

    comparative = fields.Boolean(
        string='Show previous year', default=True,
        help='B02-DN carries a "Năm trước" column. It is produced by running '
             'the same mapping over the same period one year earlier.')
    mapping_id = fields.Many2one(
        'vn.report.mapping', string='Mapping',
        domain=[('report_type', '=', 'income_statement')],
        help='Which set of statement lines to use. Leave empty for the TT200 '
             'form shipped with the module.')

    # -- comparative period --------------------------------------------
    def _comparative_filter(self):
        """The same window shifted back a year.

        Shifting the window rather than taking the whole prior fiscal year keeps
        the two columns comparable when the user reports on a quarter.
        """
        self.ensure_one()
        if not self.comparative or not self.date_from:
            return None
        return self._ledger_filter(
            date_from=self.date_from - relativedelta(years=1),
            date_to=self.date_to - relativedelta(years=1))

    # -- hooks ---------------------------------------------------------
    def _service(self):
        return IncomeStatementService(self.env)

    def _build_report(self):
        self.ensure_one()
        result = self._service().generate(
            self._ledger_filter(),
            comparative_filter=self._comparative_filter(),
            mapping_code=(self.mapping_id or self._default_mapping()).code)
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data

    def _filter_summary_fields(self):
        return ('target_move', 'comparative', 'journal_ids')

    def _default_mapping(self):
        """The mapping for this company's circular, not a hardcoded name."""
        self.ensure_one()
        return self.env['vn.report.mapping'].default_for(
            'income_statement', self.company_id)

    def _report_title(self):
        return _('Income Statement')

    def _report_form_code(self):
        return 'B02-DN'

    def _report_form_title(self):
        return 'BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH'

    def _screen_template(self):
        return 'l10n_vn_reports.income_statement_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_reports.action_report_income_statement'
