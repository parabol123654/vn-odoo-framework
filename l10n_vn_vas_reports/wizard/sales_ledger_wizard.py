# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Sổ chi tiết bán hàng (S35-DN).

Revenue per product from the 511 lines themselves, deductions from 521. The
paper form's VAT column is deliberately absent: tax belongs to the invoice,
not to the 511 line, and the Bảng kê 01/GTGT already reports it from the tax
lines — copying it here per revenue line would mean inventing an allocation.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.services.general_ledger_service import (
    SalesLedgerService,
)

#: The accounts mẫu S35-DN reads: revenue and its deductions.
SALES_ACCOUNT_PREFIXES = ('511', '521')


class VnSalesLedgerWizard(models.TransientModel):
    _name = 'vn.sales.ledger.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'Sales Ledger Report'

    account_ids = fields.Many2many(
        'account.account', string='Accounts', required=True,
        default=lambda self: self._default_sales_accounts(),
        help='Defaults to the accounts mẫu S35-DN reads: revenue (511) and '
             'its deductions (521).')
    product_ids = fields.Many2many(
        'product.product', string='Products',
        help='Leave empty to include everything sold in the period.')

    @api.model
    def _default_sales_accounts(self):
        domain = ['|'] * (len(SALES_ACCOUNT_PREFIXES) - 1)
        domain += [('code', '=like', prefix + '%')
                   for prefix in SALES_ACCOUNT_PREFIXES]
        return self.env['account.account'].search(
            [('company_id', '=', self.env.company.id)] + domain)

    # -- filter --------------------------------------------------------
    def _ledger_filter(self, **overrides):
        overrides.setdefault('account_ids', tuple(self.account_ids.ids))
        overrides.setdefault('product_ids', tuple(self.product_ids.ids))
        return super()._ledger_filter(**overrides)

    # -- hooks ---------------------------------------------------------
    def _service(self):
        return SalesLedgerService(self.env)

    def _build_report(self):
        self.ensure_one()
        if not self.account_ids:
            raise UserError(_(
                'Choose at least one revenue account.'))
        result = self._service().generate(self._ledger_filter())
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data

    def _filter_summary_fields(self):
        return ('target_move', 'journal_ids', 'account_ids', 'product_ids')

    def _xlsx_layout(self):
        return 'sales_ledger'

    def _report_title(self):
        return _('Sales Ledger')

    def _report_form_code(self):
        return 'S35-DN'

    def _report_form_title(self):
        return 'SỔ CHI TIẾT BÁN HÀNG'

    def _screen_template(self):
        return 'l10n_vn_vas_reports.sales_ledger_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_vas_reports.action_report_sales_ledger'
