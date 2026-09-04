# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Sổ quỹ tiền mặt (S07-DN) và Sổ tiền gửi ngân hàng (S08-DN).

One wizard, two statutory forms. The only difference is which accounts are in
scope, which is a filter — not a reason for a second engine, a second service or
a second template.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.core.enums import GroupBy
from odoo.addons.vn_core.services.general_ledger_service import (
    GeneralLedgerService,
)


class VnCashBookWizard(models.TransientModel):
    _name = 'vn.cash.book.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'Cash / Bank Book Report'

    book_type = fields.Selection(
        [('cash', 'Cash book (111)'),
         ('bank', 'Bank book (112)')],
        string='Book', default='cash', required=True)
    account_ids = fields.Many2many(
        'account.account', string='Accounts',
        help='Leave empty to use every account whose code starts with '
             '111 (cash) or 112 (bank).')

    _CODE_PREFIX = {'cash': '111', 'bank': '112'}

    # -- filter --------------------------------------------------------
    def _default_account_ids(self):
        """Accounts resolved by code prefix, not by hardcoded database ids.

        A customised chart of accounts keeps 111x / 112x as the statutory codes
        even when the sub-accounts differ, so the prefix is the stable handle.
        """
        self.ensure_one()
        prefix = self._CODE_PREFIX[self.book_type]
        accounts = self.env['account.account'].search([
            ('company_id', '=', self.company_id.id),
            ('code', '=like', prefix + '%'),
        ])
        if not accounts:
            raise UserError(_(
                "No account with a code starting with %s was found for %s. "
                "Pick the accounts manually, or check the chart of accounts."
            ) % (prefix, self.company_id.display_name))
        return tuple(accounts.ids)

    def _ledger_filter(self, **overrides):
        overrides.setdefault(
            'account_ids',
            tuple(self.account_ids.ids) or self._default_account_ids())
        return super()._ledger_filter(**overrides)

    # -- hooks ---------------------------------------------------------
    def _service(self):
        return GeneralLedgerService(self.env)

    def _build_report(self):
        self.ensure_one()
        result = self._service().generate(
            self._ledger_filter(),
            group_by=GroupBy.ACCOUNT,
            with_counterpart=True)
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data

    def _filter_summary_fields(self):
        return ('target_move', 'book_type', 'account_ids', 'journal_ids')

    def _xlsx_layout(self):
        return 'ledger'

    def _report_title(self):
        return _('Cash Book') if self.book_type == 'cash' else _('Bank Book')

    def _report_form_code(self):
        return 'S07-DN' if self.book_type == 'cash' else 'S08-DN'

    def _report_form_title(self):
        return ('SỔ QUỸ TIỀN MẶT' if self.book_type == 'cash'
                else 'SỔ TIỀN GỬI NGÂN HÀNG')

    def _screen_template(self):
        return 'l10n_vn_reports.cash_book_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_reports.action_report_cash_book'
