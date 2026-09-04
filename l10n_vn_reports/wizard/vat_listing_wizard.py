# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Bảng kê hoá đơn, chứng từ hàng hoá dịch vụ bán ra / mua vào.

Một wizard, hai bảng kê. Khác nhau ở chiều thuế, mà đó là một tham số chứ không
phải lý do để có thêm một engine hay một template.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.services.general_ledger_service import (
    VatPurchaseService, VatSalesService,
)


class VnVatListingWizard(models.TransientModel):
    _name = 'vn.vat.listing.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'VAT Invoice Listing'

    direction = fields.Selection(
        [('sale', 'Sales (output VAT)'),
         ('purchase', 'Purchases (input VAT)')],
        string='Listing', default='sale', required=True)
    partner_ids = fields.Many2many(
        'res.partner', string='Partners',
        help='Leave empty to include every partner.')

    # -- filter --------------------------------------------------------
    def _ledger_filter(self, **overrides):
        overrides.setdefault('partner_ids', tuple(self.partner_ids.ids))
        return super()._ledger_filter(**overrides)

    # -- hooks ---------------------------------------------------------
    def _service(self):
        return (VatSalesService(self.env) if self.direction == 'sale'
                else VatPurchaseService(self.env))

    def _build_report(self):
        self.ensure_one()
        result = self._service().generate(self._ledger_filter())
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data

    def _filter_summary_fields(self):
        return ('target_move', 'direction', 'partner_ids', 'journal_ids')

    def _xlsx_layout(self):
        return 'vat_listing'

    def _report_title(self):
        return (_('VAT Sales Listing') if self.direction == 'sale'
                else _('VAT Purchase Listing'))

    def _report_form_code(self):
        # Bảng kê is an annex to form 01/GTGT rather than a book of TT200, so it
        # carries no "Mẫu số" of its own.
        return ''

    def _report_form_title(self):
        return ('BẢNG KÊ HOÁ ĐƠN, CHỨNG TỪ HÀNG HOÁ DỊCH VỤ BÁN RA'
                if self.direction == 'sale'
                else 'BẢNG KÊ HOÁ ĐƠN, CHỨNG TỪ HÀNG HOÁ DỊCH VỤ MUA VÀO')

    def _screen_template(self):
        return 'l10n_vn_reports.vat_listing_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_reports.action_report_vat_listing'
