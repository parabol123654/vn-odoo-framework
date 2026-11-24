# -*- coding: utf-8 -*-
"""Year-end (or period-end) revaluation of foreign-currency monetary items.

Pure Python. Each balance kept in a foreign currency is restated at the
closing rate; the difference with its book value in the company currency is
the unrealised exchange gain or loss.

Advances are not monetary items and are not revalued: a credit balance on a
receivable account (the customer paid ahead) or a debit balance on a payable
account (the company paid ahead). Callers say which accounts are which.
"""

from ....core.utils.number import is_zero, round_amount

RECEIVABLE, PAYABLE = 1, -1


class RevaluationCalculator:

    @staticmethod
    def differences(balances, rates, rounding, sides=None):
        """-> ``{key: difference}`` for every balance that moves.

        :param balances: ``{(account_id, partner_id, currency_id):
            (amount_currency, balance)}``
        :param rates: ``{currency_id: company currency per foreign unit}``
        :param sides: ``{account_id: RECEIVABLE | PAYABLE}``; accounts not
            listed (cash, bank, loans) are revalued whatever their sign.
        """
        sides = sides or {}
        result = {}
        for key, (amount_currency, balance) in balances.items():
            account_id, _partner_id, currency_id = key
            if amount_currency * sides.get(account_id, 0) < 0:
                continue
            difference = round_amount(
                amount_currency * rates[currency_id] - balance, rounding)
            if not is_zero(difference, rounding):
                result[key] = difference
        return result
