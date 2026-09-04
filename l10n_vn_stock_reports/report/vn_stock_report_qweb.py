# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""QWeb PDF handler, reusing the mixin from l10n_vn_vas_reports."""

from odoo import models


class VnStockCardQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_stock_reports.report_stock_card'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'Stock Card QWeb Report'
    _wizard_model = 'vn.stock.card.wizard'
