# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Bảng cân đối kế toán (mẫu B01-DN)."""

from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.services.general_ledger_service import (
    BalanceSheetService,
)


class VnBalanceSheetWizard(models.TransientModel):
    _name = 'vn.balance.sheet.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'Balance Sheet Report'

    # A balance sheet is an as-at statement. The mixin makes date_from
    # required; it is irrelevant here and hidden in the form.
    date_from = fields.Date(required=False)

    comparative = fields.Boolean(
        string='Show opening column', default=True,
        help='B01-DN carries a "Số đầu năm" column, which is the closing '
             'balance on the day before the fiscal year began.')
    mapping_id = fields.Many2one(
        'vn.report.mapping', string='Mapping',
        domain=[('report_type', '=', 'balance_sheet')],
        help='Leave empty for the TT200 form shipped with the module.')
    show_diagnostics = fields.Boolean(
        string='Check coverage', default=True,
        help='Verify that total assets equal total capital, and list accounts '
             'carrying a balance that no item picks up.')

    # -- comparative period --------------------------------------------
    def _comparative_filter(self):
        """Closing position on the day before the fiscal year started.

        Not "the same date one year earlier": a company whose fiscal year does
        not follow the calendar would get a column that means nothing.
        """
        self.ensure_one()
        if not self.comparative:
            return None
        fiscalyear = self.company_id.compute_fiscalyear_dates(self.date_to)
        opening_day = fiscalyear['date_from'] - timedelta(days=1)
        return self._ledger_filter(date_from=None, date_to=opening_day)

    def _ledger_filter(self, **overrides):
        overrides.setdefault('date_from', None)
        return super()._ledger_filter(**overrides)

    # -- hooks ---------------------------------------------------------
    def _service(self):
        return BalanceSheetService(self.env)

    def _build_report(self):
        self.ensure_one()
        engine = self.env['vn.ledger.provider'].build_financial_statement_engine()
        try:
            return engine.compute(
                self._ledger_filter(),
                (self.mapping_id or self._default_mapping()).code,
                comparative_filter=self._comparative_filter(),
                with_diagnostics=self.show_diagnostics)
        except Exception as error:
            raise UserError(str(error))

    def _drill_date_from(self):
        """A balance sheet has no start date; open the ledger on the year.

        Opening it from inception would bury the period's movement under years
        of history, and opening it with no start date at all would drop the
        opening balance that makes the closing figure add up.
        """
        self.ensure_one()
        return self.company_id.compute_fiscalyear_dates(self.date_to)['date_from']

    def _filter_summary_fields(self):
        return ('target_move', 'comparative')

    def _default_mapping(self):
        """The mapping for this company's circular, not a hardcoded name."""
        self.ensure_one()
        return self.env['vn.report.mapping'].default_for(
            'balance_sheet', self.company_id)

    def _report_title(self):
        return _('Balance Sheet')

    def _report_form_code(self):
        return 'B01-DN'

    def _report_form_title(self):
        return 'BẢNG CÂN ĐỐI KẾ TOÁN'

    def _screen_template(self):
        return 'l10n_vn_reports.balance_sheet_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_reports.action_report_balance_sheet'
