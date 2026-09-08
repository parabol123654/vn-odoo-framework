# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""Sổ TSCĐ, Thẻ TSCĐ và Bảng tính và phân bổ khấu hao.

One wizard, three layouts — the same shape the stock and manufacturing
wizards use. The ledger-shaped fields inherited from the mixin (journals,
target move) are left unused: the asset subledger has its own notion of what
is recorded, exposed as ``include_unposted``.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.dto.filters import AssetFilter

from ..services.asset_service import (
    AssetCardService, AssetRegisterService, DepreciationAllocationService,
)


class VnAssetReportWizard(models.TransientModel):
    _name = 'vn.asset.report.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'Fixed Asset Reports'

    layout = fields.Selection(
        [('register', 'Asset register (one row per asset)'),
         ('card', 'Asset cards (one card per asset)'),
         ('allocation', 'Depreciation allocation (period cross-tab)')],
        string='Report', default='register', required=True)
    profile_ids = fields.Many2many(
        'account.asset.profile', string='Asset groups',
        help='Leave empty to include every asset group.')
    asset_ids = fields.Many2many(
        'account.asset', string='Assets',
        help='Leave empty to include every asset in scope.')
    include_unposted = fields.Boolean(
        string='Include planned depreciation', default=False,
        help='By default only depreciation that reached the ledger counts '
             '(posted entries, plus declared initial balances). Tick to '
             'widen the report to the full schedule.')

    # -- filter --------------------------------------------------------
    def _asset_filter(self):
        self.ensure_one()
        return AssetFilter(
            date_to=self.date_to,
            date_from=self.date_from,
            company_ids=tuple(self.company_id.ids),
            asset_ids=tuple(self.asset_ids.ids),
            profile_ids=tuple(self.profile_ids.ids),
            include_unposted=self.include_unposted,
        )

    # -- hooks ---------------------------------------------------------
    def _service(self):
        if self.layout == 'card':
            return AssetCardService(self.env)
        if self.layout == 'allocation':
            return DepreciationAllocationService(self.env)
        return AssetRegisterService(self.env)

    def _build_report(self):
        self.ensure_one()
        result = self._service().generate(self._asset_filter())
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data

    def _filter_summary_fields(self):
        return ('profile_ids', 'asset_ids', 'include_unposted')

    def _xlsx_layout(self):
        if self.layout == 'card':
            return 'asset_card'
        if self.layout == 'allocation':
            return 'asset_allocation'
        return 'asset_register'

    def _report_title(self):
        if self.layout == 'card':
            return _('Asset Cards')
        if self.layout == 'allocation':
            return _('Depreciation Allocation')
        return _('Asset Register')

    def _report_form_code(self):
        # 'S21-DN' is the register, 'S23-DN' the card. The allocation sheet is
        # mẫu 06-TSCĐ of the chứng từ appendix.
        if self.layout == 'card':
            return 'S23-DN'
        if self.layout == 'allocation':
            return '06-TSCĐ'
        return 'S21-DN'

    def _report_form_title(self):
        if self.layout == 'card':
            return 'THẺ TÀI SẢN CỐ ĐỊNH'
        if self.layout == 'allocation':
            return 'BẢNG TÍNH VÀ PHÂN BỔ KHẤU HAO TSCĐ'
        return 'SỔ TÀI SẢN CỐ ĐỊNH'

    def _screen_template(self):
        if self.layout == 'card':
            return 'l10n_vn_asset_reports.asset_card_screen'
        if self.layout == 'allocation':
            return 'l10n_vn_asset_reports.asset_allocation_screen'
        return 'l10n_vn_asset_reports.asset_register_screen'

    def _pdf_report_xmlid(self):
        return 'l10n_vn_asset_reports.action_report_vn_asset'
