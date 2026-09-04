# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Extends the domain provider with the fixed-asset engine.

Same extension point the inventory and manufacturing modules used: a whole
bounded context arrives by inheriting one AbstractModel, with no change to
``vn_core`` or ``l10n_vn_vas_reports``.
"""

from odoo import models

from odoo.addons.vn_core.domain.asset.engine import AssetEngine

from ..infrastructure.odoo_asset_repository import OdooAssetRepository


class LedgerProvider(models.AbstractModel):
    _inherit = 'vn.ledger.provider'

    def asset_repository_class(self):
        return OdooAssetRepository

    def asset_engine_class(self):
        return AssetEngine

    def build_asset_repository(self):
        return self.asset_repository_class()(self.env)

    def build_asset_engine(self):
        return self.asset_engine_class()(self.build_asset_repository())
