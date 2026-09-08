# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""Extends the domain provider with the manufacturing cost engine.

Fourth module, fourth bounded context added by inheriting one AbstractModel and
changing nothing in vn_core.
"""

from odoo import models

from odoo.addons.vn_core.domain.manufacturing.engine import (
    ManufacturingCostEngine,
)

from ..infrastructure.odoo_manufacturing_repository import (
    OdooManufacturingRepository,
)


class LedgerProvider(models.AbstractModel):
    _inherit = 'vn.ledger.provider'

    def manufacturing_repository_class(self):
        return OdooManufacturingRepository

    def manufacturing_engine_class(self):
        return ManufacturingCostEngine

    def build_manufacturing_repository(self):
        return self.manufacturing_repository_class()(self.env)

    def build_manufacturing_engine(self):
        return self.manufacturing_engine_class()(
            self.build_manufacturing_repository())
