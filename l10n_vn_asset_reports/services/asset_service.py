# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Fixed-asset use cases."""

from odoo.addons.vn_core.services.base_service import BaseService


class _AssetServiceBase(BaseService):

    def _engine(self):
        return self.env['vn.ledger.provider'].build_asset_engine()


class AssetRegisterService(_AssetServiceBase):
    """Sổ tài sản cố định (S21-DN)."""

    name = 'asset_register'

    def generate(self, asset_filter):
        engine = self._engine()
        return self._execute(
            lambda: engine.compute_register(asset_filter),
            date_to=asset_filter.date_to)


class AssetCardService(_AssetServiceBase):
    """Thẻ tài sản cố định (S23-DN)."""

    name = 'asset_card'

    def generate(self, asset_filter):
        engine = self._engine()
        return self._execute(
            lambda: engine.compute_cards(asset_filter),
            date_to=asset_filter.date_to)


class DepreciationAllocationService(_AssetServiceBase):
    """Bảng tính và phân bổ khấu hao TSCĐ (06-TSCĐ)."""

    name = 'depreciation_allocation'

    def generate(self, asset_filter):
        engine = self._engine()
        return self._execute(
            lambda: engine.compute_allocation(asset_filter),
            date_from=asset_filter.date_from, date_to=asset_filter.date_to)
