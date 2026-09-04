# -*- coding: utf-8 -*-
"""Inventory repository interface (Part 6 §10).

Quantity and value both come from the valuation layers, never from a quantity
source multiplied by a current unit cost. The layer is what Odoo posted to the
ledger, so a report built on it agrees with account 152/155/156 by construction;
a report that recomputes value will drift the moment a cost changes.
"""

import abc


class IInventoryRepository(abc.ABC):

    @abc.abstractmethod
    def get_products(self, inventory_filter):
        """-> Tuple[ProductDTO, ...] in scope for the filter."""

    @abc.abstractmethod
    def get_opening(self, inventory_filter):
        """Cumulative quantity and value before ``date_from``.

        -> ``{product_id: InventoryBalanceDTO}``. Stock never resets at a
        fiscal year, so this always accumulates from inception.
        """

    @abc.abstractmethod
    def get_movements(self, inventory_filter):
        """-> Iterable[InventoryMoveDTO] within the period, in date order."""

    @abc.abstractmethod
    def get_currency(self, company_ids):
        """-> CurrencyDTO of the reporting company."""
