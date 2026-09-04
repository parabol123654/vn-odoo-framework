# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Manufacturing use cases."""

from odoo.addons.vn_core.services.base_service import BaseService


class ProductionCostService(BaseService):
    """Báo cáo chi phí sản xuất và giá thành sản phẩm."""

    name = 'production_cost'

    def generate(self, manufacturing_filter):
        engine = self.env['vn.ledger.provider'].build_manufacturing_engine()
        return self._execute(
            lambda: engine.compute(manufacturing_filter),
            date_to=manufacturing_filter.date_to)


class CostCardService(BaseService):
    """Thẻ tính giá thành sản phẩm, dịch vụ (S37-DN)."""

    name = 'cost_card'

    def generate(self, manufacturing_filter):
        engine = self.env['vn.ledger.provider'].build_manufacturing_engine()
        return self._execute(
            lambda: engine.compute_cost_card(manufacturing_filter),
            date_to=manufacturing_filter.date_to)
