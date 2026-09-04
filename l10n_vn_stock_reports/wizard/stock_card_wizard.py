# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Thẻ kho và Bảng tổng hợp Nhập - Xuất - Tồn.

Reuses ``vn.report.wizard.mixin`` from ``l10n_vn_vas_reports`` so the viewer, the
PDF handoff and the form header all behave identically to the accounting books.
Only the filter differs — products and categories instead of accounts and
journals — so the ledger-shaped fields inherited from the mixin are left unused.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.dto.filters import InventoryFilter

from ..services.inventory_service import (
    InventorySummaryService, StockCardService,
)


class VnStockCardWizard(models.TransientModel):
    _name = 'vn.stock.card.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'Stock Card / Inventory Summary'

    layout = fields.Selection(
        [('summary', 'Summary (opening, in, out, closing)'),
         ('card', 'Stock card (movement detail)'),
         ('ledger', 'Stock ledger (movement detail with value)')],
        string='Detail', default='summary', required=True)
    product_ids = fields.Many2many(
        'product.product', string='Products',
        domain=[('type', '=', 'product')],
        help='Leave empty to include every storable product.')
    category_ids = fields.Many2many(
        'product.category', string='Product categories')

    # -- filter --------------------------------------------------------
    def _inventory_filter(self):
        """A stock report takes its own filter, not the ledger's.

        Products and categories have nothing to do with accounts and journals,
        and forcing one filter to serve both would leave half its fields
        meaningless in each report.
        """
        self.ensure_one()
        return InventoryFilter(
            date_to=self.date_to,
            date_from=self.date_from,
            company_ids=tuple(self.company_id.ids),
            product_ids=tuple(self.product_ids.ids),
            category_ids=tuple(self.category_ids.ids),
        )

    # -- hooks ---------------------------------------------------------
    def _service(self):
        # The ledger is the card's computation shown with its value columns,
        # so both layouts run the same service.
        return (StockCardService(self.env) if self.layout in ('card', 'ledger')
                else InventorySummaryService(self.env))

    def _build_report(self):
        self.ensure_one()
        result = self._service().generate(self._inventory_filter())
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data

    def _filter_summary_fields(self):
        return ('layout', 'product_ids', 'category_ids')

    def _xlsx_layout(self):
        if self.layout == 'ledger':
            return 'stock_ledger'
        return 'inventory'

    def _report_title(self):
        if self.layout == 'ledger':
            return _('Stock Ledger')
        return (_('Stock Card') if self.layout == 'card'
                else _('Inventory Summary'))

    def _report_form_code(self):
        # S12-DN is the stock card, S10-DN the detailed ledger with value
        # columns, S11-DN the summary: mẫu "Bảng tổng hợp chi tiết vật liệu,
        # dụng cụ, sản phẩm, hàng hóa" is exactly opening/in/out/closing per
        # product — this report with the quantity columns as a bonus.
        if self.layout == 'ledger':
            return 'S10-DN'
        return 'S12-DN' if self.layout == 'card' else 'S11-DN'

    def _report_form_title(self):
        if self.layout == 'ledger':
            return 'SỔ CHI TIẾT VẬT LIỆU, DỤNG CỤ, SẢN PHẨM, HÀNG HÓA'
        if self.layout == 'card':
            return 'THẺ KHO (SỔ KHO)'
        return ('BẢNG TỔNG HỢP CHI TIẾT VẬT LIỆU, DỤNG CỤ, '
                'SẢN PHẨM, HÀNG HÓA')

    def _screen_template(self):
        if self.layout == 'ledger':
            return 'l10n_vn_stock_reports.stock_ledger_screen'
        return ('l10n_vn_stock_reports.stock_card_screen'
                if self.layout == 'card'
                else 'l10n_vn_stock_reports.inventory_summary_screen')

    def _pdf_report_xmlid(self):
        return 'l10n_vn_stock_reports.action_report_stock_card'
