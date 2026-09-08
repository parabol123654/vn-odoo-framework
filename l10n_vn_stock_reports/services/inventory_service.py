# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""Inventory use cases."""

from odoo.addons.vn_core.services.base_service import BaseService


class _InventoryServiceBase(BaseService):

    def _engine(self):
        return self.env['vn.ledger.provider'].build_inventory_engine()


class StockCardService(_InventoryServiceBase):
    """Thẻ kho / Sổ chi tiết vật tư (S12-DN)."""

    name = 'stock_card'

    def generate(self, inventory_filter):
        engine = self._engine()
        return self._execute(
            lambda: engine.compute_stock_card(inventory_filter),
            date_to=inventory_filter.date_to)


class InventorySummaryService(_InventoryServiceBase):
    """Bảng tổng hợp Nhập - Xuất - Tồn."""

    name = 'inventory_summary'

    def generate(self, inventory_filter):
        engine = self._engine()
        return self._execute(
            lambda: engine.compute_summary(inventory_filter),
            date_to=inventory_filter.date_to)
