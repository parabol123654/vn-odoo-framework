# -*- coding: utf-8 -*-
"""Running balance calculator (Part 4 §10).

    Balance(n) = Balance(n-1) + Debit(n) - Credit(n)

One implementation, used by General Ledger, Account Ledger, Cash Book, Bank Book
and Partner Ledger alike. No report may reimplement it.
"""

from ....core.utils.number import round_amount


class RunningBalanceCalculator:

    @staticmethod
    def apply(opening_balance, lines, rounding):
        """Return the running balance after each line, in order.

        Accumulation happens on unrounded amounts and only the emitted figure is
        rounded, so a long ledger does not drift by accumulating rounding error.
        """
        running = opening_balance
        result = []
        for line in lines:
            running += line.debit - line.credit
            result.append(round_amount(running, rounding))
        return tuple(result)
