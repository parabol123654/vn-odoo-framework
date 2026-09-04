# -*- coding: utf-8 -*-
"""Manufacturing DTOs (Part 10 §11).

What this deliberately does **not** carry is a labour or overhead figure.
Odoo 14 Community posts neither to the ledger: a workcenter's ``costs_hour``
produces a statistical number that never reaches account 622 or 627, and there
is no work-in-progress account. Putting such a figure beside a material cost
that *is* journalised would produce a cost sheet where one column reconciles to
the accounts and the next does not, without saying which is which.

So this reports what the ledger actually capitalised, and says plainly that it
is direct materials only. See Part 17 §6.
"""

from datetime import date
from typing import NamedTuple, Optional, Tuple

from .common import CurrencyDTO
from .inventory import ProductDTO


class ProductionDTO(NamedTuple):
    id: int
    name: str
    product: ProductDTO
    state: str
    date_finished: Optional[date] = None
    date_started: Optional[date] = None

    @property
    def is_done(self):
        return self.state == 'done'


class ProductionCostDTO(NamedTuple):
    """One manufacturing order, costed from its valuation layers."""

    production: ProductionDTO
    material_cost: float = 0.0
    output_quantity: float = 0.0
    output_value: float = 0.0

    @property
    def variance(self):
        """What the finished goods were valued at, less what went in.

        Zero under moving average or FIFO, because Odoo values the output at
        exactly the sum of the inputs. Non-zero under standard costing, where
        the difference is the price variance — and non-zero whenever a landed
        cost was added after the fact.
        """
        return self.output_value - self.material_cost

    @property
    def unit_cost(self):
        if not self.output_quantity:
            return 0.0
        return self.output_value / self.output_quantity


class ProductCostSummaryDTO(NamedTuple):
    """The same figures rolled up per product, which is how VAS presents them."""

    product: ProductDTO
    order_count: int = 0
    material_cost: float = 0.0
    output_quantity: float = 0.0
    output_value: float = 0.0

    @property
    def unit_cost(self):
        if not self.output_quantity:
            return 0.0
        return self.output_value / self.output_quantity


class CostCardRowDTO(NamedTuple):
    """One product on the Thẻ tính giá thành (S37-DN).

    The four figures satisfy the card's own identity — opening WIP plus costs
    incurred equals finished cost plus closing WIP — only when Odoo valued the
    output at exactly the sum of the inputs, which moving average and FIFO do.
    Standard costing breaks it by the price variance, so the difference is
    exposed rather than forced to zero: a card that always balances teaches
    nobody anything.
    """

    product: ProductDTO
    #: Materials issued before the period to orders still open when it began.
    opening_wip: float = 0.0
    #: Materials issued within the period, finished orders and open ones alike.
    period_cost: float = 0.0
    #: What Odoo capitalised for the orders finished within the period.
    finished_value: float = 0.0
    finished_quantity: float = 0.0
    #: Materials issued up to the closing date to orders still open at it.
    closing_wip: float = 0.0
    finished_order_count: int = 0
    open_order_count: int = 0

    @property
    def unit_cost(self):
        if not self.finished_quantity:
            return 0.0
        return self.finished_value / self.finished_quantity

    @property
    def imbalance(self):
        """Opening + costs − finished − closing. Zero when the card balances."""
        return (self.opening_wip + self.period_cost
                - self.finished_value - self.closing_wip)


class CostCardDTO(NamedTuple):
    rows: Tuple[CostCardRowDTO, ...]
    total_opening_wip: float
    total_period_cost: float
    total_finished_value: float
    total_closing_wip: float
    currency: CurrencyDTO
    date_from: Optional[date] = None
    date_to: Optional[date] = None

    @property
    def imbalance(self):
        return (self.total_opening_wip + self.total_period_cost
                - self.total_finished_value - self.total_closing_wip)


class ManufacturingCostDTO(NamedTuple):
    orders: Tuple[ProductionCostDTO, ...]
    products: Tuple[ProductCostSummaryDTO, ...]
    material_cost: float
    output_value: float
    #: Materials issued to orders still open at the reporting date.
    work_in_progress: float
    open_order_count: int
    currency: CurrencyDTO
    date_from: Optional[date] = None
    date_to: Optional[date] = None
