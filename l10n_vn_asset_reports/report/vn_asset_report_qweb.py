# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""QWeb PDF handler, reusing the mixin from l10n_vn_vas_reports."""

from odoo import models


class VnAssetQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_asset_reports.report_vn_asset'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'Fixed Asset QWeb Report'
    _wizard_model = 'vn.asset.report.wizard'
