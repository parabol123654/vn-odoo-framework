# -*- coding: utf-8 -*-
"""Inventory Engine — Thẻ kho and Bảng tổng hợp Nhập-Xuất-Tồn (Engine 2).

Pure Python: no Odoo, no SQL. Opening balances, movements and the currency all
arrive through ``IInventoryRepository``.

One structural difference from the Ledger Engine is worth noting: stock has no
fiscal-year reset. A balance-sheet account and a stock quantity both accumulate
from inception, so the opening query needs no year-start branch at all.
"""

from ...core.exceptions import ValidationException
from ...core.utils.number import round_amount
from ...dto.inventory import (
    InventoryBalanceDTO, StockCardDTO, StockCardGroupDTO, StockCardLineDTO,
)
from .calculators.running_stock import RunningStockCalculator

_EMPTY = InventoryBalanceDTO()


class InventoryEngine:

    def __init__(self, repository):
        self._repo = repository

    # ==================================================================
    # Public API
    # ==================================================================
    def compute_stock_card(self, inventory_filter, with_lines=True):
        """Thẻ kho (S12-DN) when ``with_lines``, Bảng tổng hợp N-X-T otherwise.

        The two reports are the same computation at different detail, so they
        share one method rather than one engine each.
        """
        self._validate(inventory_filter)
        currency = self._repo.get_currency(inventory_filter.company_ids)
        rounding = currency.rounding

        products = {p.id: p for p in self._repo.get_products(inventory_filter)}
        opening = self._repo.get_opening(inventory_filter)
        movements = tuple(self._repo.get_movements(inventory_filter))

        buckets = {}
        for move in movements:
            buckets.setdefault(move.product_id, []).append(move)

        groups = []
        for product_id in set(buckets) | set(opening):
            product = products.get(product_id)
            if product is None:
                continue
            groups.append(self._build_group(
                product, opening.get(product_id, _EMPTY),
                buckets.get(product_id, ()), rounding, with_lines))

        groups = [g for g in groups if self._is_material(g)]
        groups.sort(key=lambda g: (g.product.code or '', g.product.name))

        totals = InventoryBalanceDTO(
            quantity=0.0,
            value=round_amount(sum(g.closing.value for g in groups), rounding),
        )
        return StockCardDTO(
            groups=tuple(groups),
            totals=totals,
            currency=currency,
            date_from=inventory_filter.date_from,
            date_to=inventory_filter.date_to,
        )

    def compute_summary(self, inventory_filter):
        """Bảng tổng hợp Nhập - Xuất - Tồn: totals only, no card lines."""
        return self.compute_stock_card(inventory_filter, with_lines=False)

    # ==================================================================
    # Internals
    # ==================================================================
    @staticmethod
    def _validate(inventory_filter):
        if not inventory_filter.company_ids:
            raise ValidationException('No company supplied in the filter.')
        if (inventory_filter.date_from
                and inventory_filter.date_from > inventory_filter.date_to):
            raise ValidationException('date_from must precede date_to.')

    def _build_group(self, product, opening, moves, rounding, with_lines):
        incoming, outgoing = _EMPTY, _EMPTY
        for move in moves:
            moved_in, moved_out = RunningStockCalculator.split(move, rounding)
            incoming = incoming.plus(moved_in)
            outgoing = outgoing.plus(moved_out)

        closing = InventoryBalanceDTO(
            quantity=round_amount(
                opening.quantity + incoming.quantity - outgoing.quantity,
                RunningStockCalculator.QUANTITY_ROUNDING),
            value=round_amount(
                opening.value + incoming.value - outgoing.value, rounding),
        )

        lines = ()
        if with_lines and moves:
            running = RunningStockCalculator.apply(opening, moves, rounding)
            lines = tuple(
                StockCardLineDTO(
                    source=move,
                    incoming=RunningStockCalculator.split(move, rounding)[0],
                    outgoing=RunningStockCalculator.split(move, rounding)[1],
                    running=running[position],
                )
                for position, move in enumerate(moves)
            )

        return StockCardGroupDTO(
            product=product,
            opening=InventoryBalanceDTO(
                round_amount(opening.quantity,
                             RunningStockCalculator.QUANTITY_ROUNDING),
                round_amount(opening.value, rounding)),
            incoming=incoming,
            outgoing=outgoing,
            closing=closing,
            lines=lines,
        )

    @staticmethod
    def _is_material(group):
        """Drop products that neither opened, moved, nor closed with anything.

        A chart of a thousand products would otherwise print a thousand empty
        rows.
        """
        return any((group.opening.quantity, group.opening.value,
                    group.incoming.quantity, group.outgoing.quantity,
                    group.closing.quantity, group.closing.value))
