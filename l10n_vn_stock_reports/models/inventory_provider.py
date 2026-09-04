# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Extends the domain provider with the inventory engine.

This is the extension point built into ``vn_core`` doing its job: a separate
module adds a whole bounded context by inheriting one AbstractModel, without
touching framework code. Resolution stays per-database, so a company that has
not installed this module simply never sees the method.
"""

from odoo import models

from odoo.addons.vn_core.domain.inventory.engine import InventoryEngine

from ..infrastructure.odoo_inventory_repository import OdooInventoryRepository


class LedgerProvider(models.AbstractModel):
    _inherit = 'vn.ledger.provider'

    def inventory_repository_class(self):
        return OdooInventoryRepository

    def inventory_engine_class(self):
        return InventoryEngine

    def build_inventory_repository(self):
        return self.inventory_repository_class()(self.env)

    def build_inventory_engine(self):
        return self.inventory_engine_class()(self.build_inventory_repository())
