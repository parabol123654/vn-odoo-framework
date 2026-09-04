# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Bảng phân bổ nguyên liệu, vật liệu, công cụ, dụng cụ (mẫu 07-VT).

Built from the general ledger — the credit lines of 152/153/242 and where
their debit side went — so every column reconciles to the "Ghi Có" of that
account. That also states the report's limit honestly: on a database that
values stock periodically (no real-time posting), issues write no journal
entries and this table is empty, because in the books nothing was allocated.

Lives beside the expense ledger for the same Part 16 §4 reason: it reads
nothing but the ledger, so it must not cost anyone a stock or mrp dependency.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.services.general_ledger_service import (
    MaterialAllocationService,
)

#: The "Ghi Có các TK" of mẫu 07-VT: materials, tools, and the prepaid account
#: tools are amortised from. Prefixes, so detail accounts (1521...) are covered.
SOURCE_ACCOUNT_PREFIXES = ('152', '153', '242')


class VnMaterialAllocationWizard(models.TransientModel):
    _name = 'vn.material.allocation.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'Material Allocation Sheet'

    account_ids = fields.Many2many(
        'account.account', string='Credited accounts', required=True,
        default=lambda self: self._default_source_accounts(),
        help='The "Ghi Có" side of the sheet. Defaults to the accounts mẫu '
             '07-VT names: 152, 153 and 242.')

    @api.model
    def _default_source_accounts(self):
        domain = ['|'] * (len(SOURCE_ACCOUNT_PREFIXES) - 1)
        domain += [('code', '=like', prefix + '%')
                   for prefix in SOURCE_ACCOUNT_PREFIXES]
        return self.env['account.account'].search(
            [('company_id', '=', self.env.company.id)] + domain)

    # -- filter --------------------------------------------------------
    def _ledger_filter(self, **overrides):
        overrides.setdefault('account_ids', tuple(self.account_ids.ids))
        return super()._ledger_filter(**overrides)

    # -- hooks ---------------------------------------------------------
    def _service(self):
        return MaterialAllocationService(self.env)

    def _build_report(self):
        self.ensure_one()
        if not self.account_ids:
            raise UserError(_(
                'Choose at least one credited account. An allocation sheet '
                'needs to know what it allocates.'))
        result = self._service().generate(self._ledger_filter())
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data

    def _filter_summary_fields(self):
        return ('target_move', 'journal_ids', 'account_ids')

    def _xlsx_layout(self):
        return 'allocation'

    def _report_title(self):
        return _('Material Allocation')

    def _report_form_code(self):
        return '07-VT'

    def _report_form_title(self):
        return 'BẢNG PHÂN BỔ NGUYÊN LIỆU, VẬT LIỆU, CÔNG CỤ, DỤNG CỤ'

    def _screen_template(self):
        return 'l10n_vn_vas_reports.material_allocation_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_vas_reports.action_report_material_allocation'
