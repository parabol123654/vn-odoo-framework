# -*- coding: utf-8 -*-
"""Inventory DTOs (Part 10 §9).

Quantity and value travel together everywhere. A Vietnamese stock report that
carries quantity alone is useless — Thẻ kho and Bảng tổng hợp Nhập-Xuất-Tồn both
print value beside every quantity — and recomputing value as quantity times a
current unit cost is the classic way to produce a stock report that disagrees
with the general ledger.
"""

from datetime import date
from typing import NamedTuple, Optional, Tuple

from .common import CurrencyDTO


class ProductDTO(NamedTuple):
    id: int
    code: str
    name: str
    uom_name: str = ''
    category_name: str = ''

    @property
    def display_name(self):
        return '[%s] %s' % (self.code, self.name) if self.code else self.name


class InventoryMoveDTO(NamedTuple):
    """One valuation layer: a quantity and the value that moved with it."""

    id: int
    date: date
    product_id: int
    quantity: float
    value: float
    unit_cost: float = 0.0
    reference: str = ''
    description: str = ''
    partner_name: str = ''
    move_id: Optional[int] = None
    #: Account codes on the other side of the layer's journal entry, e.g.
    #: "331" on a receipt or "154, 632" on an issue. S10-DN prints this as
    #: "TK đối ứng"; empty when the layer posted no entry (periodic inventory).
    counterpart: str = ''

    @property
    def is_incoming(self):
        return self.quantity > 0


class InventoryBalanceDTO(NamedTuple):
    quantity: float = 0.0
    value: float = 0.0

    def plus(self, other):
        return InventoryBalanceDTO(self.quantity + other.quantity,
                                   self.value + other.value)


class StockCardLineDTO(NamedTuple):
    """A Thẻ kho row: what moved, and what remained after it."""

    source: InventoryMoveDTO
    incoming: InventoryBalanceDTO
    outgoing: InventoryBalanceDTO
    running: InventoryBalanceDTO

    @property
    def date(self):
        return self.source.date

    @property
    def reference(self):
        return self.source.reference

    @property
    def description(self):
        return self.source.description

    @property
    def unit_cost(self):
        return self.source.unit_cost

    @property
    def counterpart(self):
        return self.source.counterpart


class StockCardGroupDTO(NamedTuple):
    product: ProductDTO
    opening: InventoryBalanceDTO
    incoming: InventoryBalanceDTO
    outgoing: InventoryBalanceDTO
    closing: InventoryBalanceDTO
    lines: Tuple[StockCardLineDTO, ...] = ()

    @property
    def average_unit_cost(self):
        """Period-end weighted average, for comparison only.

        Odoo's AVCO is a *moving* average recomputed at each receipt, while much
        Vietnamese practice uses bình quân cuối kỳ — one average struck at the
        end of the month. The two give different closing values for the same
        movements. This exposes the period-end figure so the difference is
        visible rather than a surprise at the year end; the report's own value
        column stays faithful to what Odoo posted to the ledger.
        """
        total_quantity = self.opening.quantity + self.incoming.quantity
        if not total_quantity:
            return 0.0
        return (self.opening.value + self.incoming.value) / total_quantity


class StockCardDTO(NamedTuple):
    groups: Tuple[StockCardGroupDTO, ...]
    totals: InventoryBalanceDTO
    currency: CurrencyDTO
    date_from: Optional[date] = None
    date_to: Optional[date] = None
