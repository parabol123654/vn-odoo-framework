# -*- coding: utf-8 -*-
"""Running stock calculator.

    Tồn(n) = Tồn(n-1) + Nhập(n) - Xuất(n)

Applied to quantity and value together. One implementation, used by Thẻ kho and
by the Nhập-Xuất-Tồn summary alike.
"""

from ....core.utils.number import round_amount
from ....dto.inventory import InventoryBalanceDTO


class RunningStockCalculator:

    #: Quantities are not money; they keep their own precision.
    QUANTITY_ROUNDING = 0.001

    @classmethod
    def split(cls, move, rounding):
        """A layer is incoming or outgoing; it is never both.

        Odoo signs the layer, so the split is on that sign rather than on the
        source document — a return on a purchase is an outgoing movement even
        though it sits on an incoming picking.
        """
        quantity = round_amount(abs(move.quantity), cls.QUANTITY_ROUNDING)
        value = round_amount(abs(move.value), rounding)
        empty = InventoryBalanceDTO()
        moved = InventoryBalanceDTO(quantity, value)
        return (moved, empty) if move.is_incoming else (empty, moved)

    @classmethod
    def apply(cls, opening, moves, rounding):
        """Return the running balance after each movement, in order."""
        quantity, value = opening.quantity, opening.value
        result = []
        for move in moves:
            quantity += move.quantity
            value += move.value
            result.append(InventoryBalanceDTO(
                round_amount(quantity, cls.QUANTITY_ROUNDING),
                round_amount(value, rounding)))
        return tuple(result)
