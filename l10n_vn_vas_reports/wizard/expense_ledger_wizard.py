# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Sổ chi phí sản xuất, kinh doanh (S36-DN).

Lives in the accounting module rather than beside the manufacturing reports on
purpose: the book is prescribed for 641, 642, 242 and 335 as much as for the
production accounts, so a trading company keeping ordinary books needs it too,
and it reads nothing but the general ledger (Part 16 §4 — no dependency is
added for a report that does not need one).
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.services.general_ledger_service import (
    ExpenseLedgerService,
)

#: The accounts mẫu S36-DN names on its own header. Prefixes, so a chart with
#: detail accounts (6421, 6422...) is covered without listing them here.
EXPENSE_ACCOUNT_PREFIXES = (
    '154', '242', '335', '621', '622', '623', '627', '631', '632', '641',
    '642',
)


class VnExpenseLedgerWizard(models.TransientModel):
    _name = 'vn.expense.ledger.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'Expense Ledger Report'

    account_ids = fields.Many2many(
        'account.account', string='Accounts', required=True,
        default=lambda self: self._default_expense_accounts(),
        help='Defaults to the accounts form S36-DN itself names: 154, 242, '
             '335, 621, 622, 623, 627, 631, 632, 641, 642.')

    @api.model
    def _default_expense_accounts(self):
        domain = ['|'] * (len(EXPENSE_ACCOUNT_PREFIXES) - 1)
        domain += [('code', '=like', prefix + '%')
                   for prefix in EXPENSE_ACCOUNT_PREFIXES]
        return self.env['account.account'].search(
            [('company_id', '=', self.env.company.id)] + domain)

    # -- filter --------------------------------------------------------
    def _ledger_filter(self, **overrides):
        overrides.setdefault('account_ids', tuple(self.account_ids.ids))
        return super()._ledger_filter(**overrides)

    # -- hooks ---------------------------------------------------------
    def _service(self):
        return ExpenseLedgerService(self.env)

    def _build_report(self):
        self.ensure_one()
        if not self.account_ids:
            raise UserError(_(
                'Choose at least one account. An expense ledger over every '
                'account of the chart would not be an expense ledger.'))
        result = self._service().generate(self._ledger_filter())
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data

    def _filter_summary_fields(self):
        return ('target_move', 'journal_ids', 'account_ids')

    def _xlsx_layout(self):
        return 'expense_ledger'

    def _report_title(self):
        return _('Expense Ledger')

    def _report_form_code(self):
        return 'S36-DN'

    def _report_form_title(self):
        return 'SỔ CHI PHÍ SẢN XUẤT, KINH DOANH'

    def _screen_template(self):
        return 'l10n_vn_vas_reports.expense_ledger_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_vas_reports.action_report_expense_ledger'
