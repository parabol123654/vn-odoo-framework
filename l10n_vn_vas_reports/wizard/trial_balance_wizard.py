# -*- coding: utf-8 -*-
# Target: Odoo 15.0 Community Edition
"""Bảng cân đối phát sinh wizard."""

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.services.general_ledger_service import (
    TrialBalanceService,
)


class VnTrialBalanceWizard(models.TransientModel):
    _name = 'vn.trial.balance.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'Trial Balance Report'

    show_all_accounts = fields.Boolean(
        string='Include accounts with no activity', default=False,
        help='Prints the whole chart of accounts, including untouched ones.')

    def _service(self):
        return TrialBalanceService(self.env)

    def _filter_summary_fields(self):
        return ('target_move', 'journal_ids', 'account_ids', 'include_empty')

    def _xlsx_layout(self):
        return 'trial_balance'

    def _report_title(self):
        return _('Trial Balance')

    def _report_form_code(self):
        # Under TT133 this is the F01-DNN that goes to the tax authority with
        # the statements (Điều 71, Điều 83); S06-DNN is a different book.
        return self._by_circular({'TT200': 'S06-DN', 'TT133': 'F01-DNN'})

    def _report_form_title(self):
        return self._by_circular({'TT200': 'BẢNG CÂN ĐỐI SỐ PHÁT SINH',
                                  'TT133': 'BẢNG CÂN ĐỐI TÀI KHOẢN'})

    def _screen_template(self):
        return 'l10n_vn_vas_reports.trial_balance_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_vas_reports.action_report_trial_balance'

    def _build_report(self):
        self.ensure_one()
        result = self._service().generate(
            self._ledger_filter(), include_empty=self.show_all_accounts)
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data
