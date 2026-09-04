# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Sổ Nhật ký chung (mẫu S03a-DN)."""

from odoo import _, models

from odoo.addons.vn_core.services.general_ledger_service import (
    GeneralJournalService,
)


class VnGeneralJournalWizard(models.TransientModel):
    _name = 'vn.general.journal.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'General Journal Report'

    # No grouping options: the statutory book is strictly chronological, and
    # entries of one voucher must stay adjacent. Offering a "group by" here
    # would produce something that is no longer S03a-DN.

    def _service(self):
        return GeneralJournalService(self.env)

    def _filter_summary_fields(self):
        return ('target_move', 'journal_ids')

    def _xlsx_layout(self):
        return 'ledger'

    def _report_title(self):
        return _('General Journal')

    def _report_form_code(self):
        return 'S03a-DN'

    def _report_form_title(self):
        return 'SỔ NHẬT KÝ CHUNG'

    def _screen_template(self):
        return 'l10n_vn_reports.general_journal_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_reports.action_report_general_journal'
