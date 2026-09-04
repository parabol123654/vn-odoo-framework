# -*- coding: utf-8 -*-
"""Closing balance calculator (Part 4 §11).

    Closing = Opening + Debit - Credit
"""

from ....core.utils.number import round_amount


class ClosingBalanceCalculator:

    @staticmethod
    def compute(opening_balance, movement, rounding):
        """``movement`` is a ``BalanceDTO`` for the period."""
        return round_amount(
            opening_balance + movement.debit - movement.credit, rounding)
