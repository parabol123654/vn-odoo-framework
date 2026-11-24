# -*- coding: utf-8 -*-
"""Period-end closing entries (kết chuyển cuối kỳ).

Pure Python. Sales deductions (521) are first moved onto sales (511), then
every revenue and expense account is emptied into 911 and the net of 911 is
moved to retained earnings (4212).

Lines come in pairs, source first: ``(account emptied, -balance)`` then
``(account receiving it, balance)``. A caller can label each pair "from X to
Y" without knowing which side is debit, and every pair sums to zero.

Balances are fiscal-year-to-date and include earlier closing entries of the
same year, so closing twice finds nothing the second time.
"""

from ....core.utils.number import is_zero, round_amount


class PeriodClosingCalculator:
    """Lines of the deduction transfer and of the closing entry."""

    @staticmethod
    def _pairs(balances, account_ids, target_id, rounding):
        """-> (lines, total) emptying each account into ``target_id``."""
        lines, total = [], 0.0
        for account_id in sorted(set(account_ids)):
            balance = round_amount(balances.get(account_id, 0.0), rounding)
            if is_zero(balance, rounding):
                continue
            lines += [(account_id, -balance), (target_id, balance)]
            total += balance
        return lines, round_amount(total, rounding)

    @staticmethod
    def deduction_transfer(balances, deduction_ids, sales_account_id, rounding):
        """-> ``((account_id, amount), ...)`` moving every deduction balance
        onto ``sales_account_id``; ``()`` when nothing to move.

        ``amount`` follows the ledger sign (debit positive).
        """
        lines, _total = PeriodClosingCalculator._pairs(
            balances, deduction_ids, sales_account_id, rounding
        )
        return tuple(lines)

    @staticmethod
    def closing(
        balances, account_ids, result_account_id, retained_account_id, rounding
    ):
        """-> ``((account_id, amount), ...)`` emptying ``account_ids`` into
        the result account, then the result account into retained earnings.

        Profit leaves a credit on the result account and is moved to the
        credit of retained earnings; a loss to its debit. A balance already
        on the result account (a partial transfer by hand, an imported
        opening) is moved with it, so the result account always ends at
        zero. ``()`` when every balance is zero.
        """
        lines, net = PeriodClosingCalculator._pairs(
            balances,
            set(account_ids) - {result_account_id},
            result_account_id,
            rounding,
        )
        net = round_amount(net + balances.get(result_account_id, 0.0), rounding)
        if not is_zero(net, rounding):
            lines += [(result_account_id, -net), (retained_account_id, net)]
        return tuple(lines)

    @staticmethod
    def apply(balances, lines):
        """-> a new ``{account_id: balance}`` with ``lines`` posted.

        The closing reads balances after the deduction transfer, which has not
        been posted yet when it is computed.
        """
        result = dict(balances)
        for account_id, amount in lines:
            result[account_id] = result.get(account_id, 0.0) + amount
        return result
