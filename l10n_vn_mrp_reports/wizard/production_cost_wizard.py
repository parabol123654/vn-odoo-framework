# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Báo cáo chi phí sản xuất và giá thành sản phẩm."""

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.dto.filters import ManufacturingFilter

from ..services.manufacturing_service import (
    CostCardService, ProductionCostService,
)


class VnProductionCostWizard(models.TransientModel):
    _name = 'vn.production.cost.wizard'
    _inherit = 'vn.report.wizard.mixin'
    _description = 'Production Cost Report'

    layout = fields.Selection(
        [('product', 'By product'),
         ('order', 'By manufacturing order'),
         ('cost_card', 'Cost card (opening WIP, costs, finished, closing WIP)')],
        string='Detail', default='product', required=True)
    product_ids = fields.Many2many(
        'product.product', string='Products',
        domain=[('type', '=', 'product')],
        help='Leave empty to include everything manufactured in the period.')
    category_ids = fields.Many2many(
        'product.category', string='Product categories')
    include_open = fields.Boolean(
        string='Show work in progress', default=True,
        help='Report the materials already issued to orders that had not '
             'finished by the reporting date. Odoo 14 Community has no '
             'work-in-progress account, so this figure exists nowhere in the '
             'ledger and is derived from those orders.')

    # -- filter --------------------------------------------------------
    def _manufacturing_filter(self):
        self.ensure_one()
        return ManufacturingFilter(
            date_to=self.date_to,
            date_from=self.date_from,
            company_ids=tuple(self.company_id.ids),
            product_ids=tuple(self.product_ids.ids),
            category_ids=tuple(self.category_ids.ids),
            include_open=self.include_open,
        )

    # -- hooks ---------------------------------------------------------
    def _service(self):
        return (CostCardService(self.env) if self.layout == 'cost_card'
                else ProductionCostService(self.env))

    def _build_report(self):
        self.ensure_one()
        result = self._service().generate(self._manufacturing_filter())
        if not result.success:
            raise UserError('\n'.join(result.errors))
        return result.data

    def _filter_summary_fields(self):
        return ('layout', 'product_ids', 'category_ids', 'include_open')

    def _xlsx_layout(self):
        if self.layout == 'cost_card':
            return 'cost_card'
        return 'production_cost'

    def _report_title(self):
        return (_('Cost Card') if self.layout == 'cost_card'
                else _('Production Cost'))

    def _report_form_code(self):
        # The production cost summary is a management report; TT200 prescribes
        # no form for it. The cost card is mẫu S37-DN.
        return 'S37-DN' if self.layout == 'cost_card' else ''

    def _report_form_title(self):
        return ('THẺ TÍNH GIÁ THÀNH SẢN PHẨM, DỊCH VỤ'
                if self.layout == 'cost_card'
                else 'BÁO CÁO CHI PHÍ SẢN XUẤT VÀ GIÁ THÀNH SẢN PHẨM')

    def _screen_template(self):
        if self.layout == 'cost_card':
            return 'l10n_vn_mrp_reports.cost_card_screen'
        return ('l10n_vn_mrp_reports.production_cost_order_screen'
                if self.layout == 'order'
                else 'l10n_vn_mrp_reports.production_cost_product_screen')

    def _pdf_report_xmlid(self):
        return 'l10n_vn_mrp_reports.action_report_production_cost'
