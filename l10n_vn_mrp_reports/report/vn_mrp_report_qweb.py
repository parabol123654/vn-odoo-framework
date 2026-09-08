# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""QWeb PDF handler, reusing the mixin from l10n_vn_vas_reports."""

from odoo import models


class VnProductionCostQwebReport(models.AbstractModel):
    _name = 'report.l10n_vn_mrp_reports.report_production_cost'
    _inherit = 'report.vn.qweb.mixin'
    _description = 'Production Cost QWeb Report'
    _wizard_model = 'vn.production.cost.wizard'
