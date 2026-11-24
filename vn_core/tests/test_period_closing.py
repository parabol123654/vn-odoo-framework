# -*- coding: utf-8 -*-
"""Period-end closing entries (kết chuyển cuối kỳ) calculator tests. No Odoo.

Account ids double as VAS codes here so the expected lines read like the
textbook entries: 521 into 511, then everything into 911, then 911 into 4212.
"""

import unittest
from collections import defaultdict

from ..domain.ledger.calculators.period_closing import PeriodClosingCalculator

SALES, DEDUCTION_A, DEDUCTION_B = 511, 5211, 5213
FINANCE_INCOME, OTHER_INCOME = 515, 711
COST, SELLING, ADMIN = 632, 641, 642
RESULT, RETAINED = 911, 4212
RECEIVABLE = 131

ROUNDING = 0.01


def _net(lines):
    """-> ``{account_id: summed amount}``: order-independent view of lines."""
    totals = defaultdict(float)
    for account_id, amount in lines:
        totals[account_id] += amount
    return {key: round(value, 2) for key, value in totals.items()}


class TestDeductionTransfer(unittest.TestCase):

    def test_moves_the_deduction_onto_sales(self):
        """Nợ 511 / Có 521: credit 521 by its debit balance, debit 511."""
        balances = {SALES: -1000.0, DEDUCTION_A: 100.0, RECEIVABLE: 900.0}
        lines = PeriodClosingCalculator.deduction_transfer(
            balances, [DEDUCTION_A], SALES, ROUNDING
        )
        self.assertEqual(_net(lines), {DEDUCTION_A: -100.0, SALES: 100.0})

    def test_several_deduction_accounts(self):
        balances = {SALES: -1000.0, DEDUCTION_A: 60.0, DEDUCTION_B: 40.0}
        lines = PeriodClosingCalculator.deduction_transfer(
            balances, [DEDUCTION_A, DEDUCTION_B], SALES, ROUNDING
        )
        self.assertEqual(
            _net(lines), {DEDUCTION_A: -60.0, DEDUCTION_B: -40.0, SALES: 100.0}
        )
        self.assertAlmostEqual(sum(amount for _a, amount in lines), 0.0)

    def test_a_credit_balance_is_moved_too(self):
        """A reversed deduction leaves a credit on 521; it still goes to 511."""
        balances = {DEDUCTION_A: -25.0}
        lines = PeriodClosingCalculator.deduction_transfer(
            balances, [DEDUCTION_A], SALES, ROUNDING
        )
        self.assertEqual(_net(lines), {DEDUCTION_A: 25.0, SALES: -25.0})

    def test_nothing_when_zero(self):
        balances = {SALES: -1000.0, DEDUCTION_A: 0.0}
        self.assertEqual(
            tuple(
                PeriodClosingCalculator.deduction_transfer(
                    balances, [DEDUCTION_A], SALES, ROUNDING
                )
            ),
            (),
        )

    def test_nothing_when_the_deduction_has_no_balance_at_all(self):
        self.assertEqual(
            tuple(
                PeriodClosingCalculator.deduction_transfer(
                    {SALES: -1000.0}, [DEDUCTION_A], SALES, ROUNDING
                )
            ),
            (),
        )

    def test_nothing_without_deduction_accounts(self):
        """TT133: the deduction expression is empty."""
        self.assertEqual(
            tuple(
                PeriodClosingCalculator.deduction_transfer(
                    {SALES: -1000.0, DEDUCTION_A: 50.0}, [], SALES, ROUNDING
                )
            ),
            (),
        )

    def test_rounds_to_the_currency(self):
        balances = {DEDUCTION_A: 100.004, DEDUCTION_B: 0.004}
        lines = PeriodClosingCalculator.deduction_transfer(
            balances, [DEDUCTION_A, DEDUCTION_B], SALES, ROUNDING
        )
        self.assertEqual(_net(lines), {DEDUCTION_A: -100.0, SALES: 100.0})
        for _account, amount in lines:
            self.assertEqual(amount, round(amount, 2))

    def test_rounds_to_whole_dong(self):
        lines = PeriodClosingCalculator.deduction_transfer(
            {DEDUCTION_A: 1000.4}, [DEDUCTION_A], SALES, 1.0
        )
        self.assertEqual(_net(lines), {DEDUCTION_A: -1000.0, SALES: 1000.0})


class TestClosing(unittest.TestCase):

    in_scope = [ADMIN, SALES, COST, FINANCE_INCOME]  # deliberately unsorted

    def _close(self, balances, account_ids=None, rounding=ROUNDING):
        return tuple(
            PeriodClosingCalculator.closing(
                balances,
                self.in_scope if account_ids is None else account_ids,
                RESULT,
                RETAINED,
                rounding,
            )
        )

    def test_profit_lines_in_ascending_account_order(self):
        balances = {SALES: -1000.0, FINANCE_INCOME: -30.0, COST: 600.0, ADMIN: 150.0}
        self.assertEqual(
            self._close(balances),
            (
                (SALES, 1000.0),
                (RESULT, -1000.0),
                (FINANCE_INCOME, 30.0),
                (RESULT, -30.0),
                (COST, -600.0),
                (RESULT, 600.0),
                (ADMIN, -150.0),
                (RESULT, 150.0),
                # Profit 280: Nợ 911 / Có 4212.
                (RESULT, 280.0),
                (RETAINED, -280.0),
            ),
        )

    def test_loss_debits_retained_earnings(self):
        balances = {SALES: -100.0, COST: 300.0}
        self.assertEqual(
            self._close(balances),
            (
                (SALES, 100.0),
                (RESULT, -100.0),
                (COST, -300.0),
                (RESULT, 300.0),
                # Loss 200: Nợ 4212 / Có 911.
                (RESULT, -200.0),
                (RETAINED, 200.0),
            ),
        )

    def test_every_account_is_zeroed_and_911_is_left_empty(self):
        balances = {SALES: -1000.0, FINANCE_INCOME: -30.0, COST: 600.0, ADMIN: 150.0}
        net = _net(self._close(balances))
        for account_id in self.in_scope:
            self.assertEqual(balances[account_id] + net[account_id], 0.0)
        self.assertEqual(net[RESULT], 0.0)
        self.assertEqual(net[RETAINED], -280.0)

    def test_lines_sum_to_zero(self):
        balances = {SALES: -1234.56, FINANCE_INCOME: -7.89, COST: 987.65, ADMIN: 43.21}
        lines = self._close(balances)
        self.assertAlmostEqual(sum(amount for _a, amount in lines), 0.0, places=6)

    def test_break_even_has_no_retained_earnings_pair(self):
        balances = {SALES: -100.0, COST: 100.0}
        self.assertEqual(
            self._close(balances),
            (
                (SALES, 100.0),
                (RESULT, -100.0),
                (COST, -100.0),
                (RESULT, 100.0),
            ),
        )

    def test_ignores_accounts_outside_the_given_ids(self):
        balances = {SALES: -500.0, COST: 200.0, RECEIVABLE: 300.0, OTHER_INCOME: -40.0}
        lines = self._close(balances)
        accounts = {account_id for account_id, _amount in lines}
        self.assertNotIn(RECEIVABLE, accounts)
        self.assertNotIn(OTHER_INCOME, accounts)
        self.assertEqual(lines[-2:], ((RESULT, 300.0), (RETAINED, -300.0)))

    def test_skips_zero_and_missing_accounts(self):
        balances = {SALES: -500.0, COST: 0.0}  # ADMIN, 515 absent
        self.assertEqual(
            self._close(balances),
            (
                (SALES, 500.0),
                (RESULT, -500.0),
                (RESULT, 500.0),
                (RETAINED, -500.0),
            ),
        )

    def test_empty_when_everything_is_zero(self):
        self.assertEqual(self._close({SALES: 0.0, COST: 0.0}), ())
        self.assertEqual(self._close({}), ())
        self.assertEqual(self._close({RECEIVABLE: 100.0}), ())

    def test_empty_when_balances_round_to_zero(self):
        self.assertEqual(self._close({SALES: -0.004, COST: 0.003}), ())

    def test_uses_rounded_balances(self):
        balances = {SALES: -1000.004, COST: 600.001}
        self.assertEqual(
            self._close(balances),
            (
                (SALES, 1000.0),
                (RESULT, -1000.0),
                (COST, -600.0),
                (RESULT, 600.0),
                (RESULT, 400.0),
                (RETAINED, -400.0),
            ),
        )

    def test_rounds_to_whole_dong(self):
        balances = {SALES: -1000000.4, COST: 400000.3}
        self.assertEqual(
            self._close(balances, rounding=1.0),
            (
                (SALES, 1000000.0),
                (RESULT, -1000000.0),
                (COST, -400000.0),
                (RESULT, 400000.0),
                (RESULT, 600000.0),
                (RETAINED, -600000.0),
            ),
        )

    def test_existing_911_balance_joins_the_net_result(self):
        """A balance already on 911 (e.g. a manual Nợ 511 / Có 911) is part of
        the result moved to 4212, so 911 ends at zero."""
        balances = {SALES: -300.0, COST: 100.0, RESULT: 50.0}
        self.assertEqual(
            self._close(balances),
            (
                (SALES, 300.0),
                (RESULT, -300.0),
                (COST, -100.0),
                (RESULT, 100.0),
                # N = -300 + 100 + 50 = -150: profit 150.
                (RESULT, 150.0),
                (RETAINED, -150.0),
            ),
        )
        net = _net(self._close(balances))
        self.assertEqual(balances[RESULT] + net[RESULT], 0.0)

    def test_only_911_has_a_balance(self):
        """Nothing left to close but 911 itself: just the 911 → 4212 pair."""
        self.assertEqual(
            self._close({RESULT: 50.0, SALES: 0.0}),
            ((RESULT, -50.0), (RETAINED, 50.0)),
        )
        self.assertEqual(
            self._close({RESULT: -75.0}),
            ((RESULT, 75.0), (RETAINED, -75.0)),
        )


class TestFullClosing(unittest.TestCase):
    """Deductions first, then the closing, as the wizard does."""

    @unittest.skipUnless(
        hasattr(PeriodClosingCalculator, "apply"),
        "optional apply() helper not implemented",
    )
    def test_apply_returns_a_new_dict(self):
        balances = {SALES: -1000.0, DEDUCTION_A: 100.0}
        lines = ((DEDUCTION_A, -100.0), (SALES, 100.0), (RESULT, 5.0))
        result = PeriodClosingCalculator.apply(balances, lines)
        self.assertEqual(balances, {SALES: -1000.0, DEDUCTION_A: 100.0})
        self.assertIsNot(result, balances)
        self.assertEqual(result[SALES], -900.0)
        self.assertEqual(result.get(DEDUCTION_A, 0.0), 0.0)
        self.assertEqual(result[RESULT], 5.0)

    @unittest.skipUnless(
        hasattr(PeriodClosingCalculator, "apply"),
        "optional apply() helper not implemented",
    )
    def test_deduction_then_closing_leaves_only_retained_earnings(self):
        calc = PeriodClosingCalculator
        balances = {
            SALES: -1000.0,
            DEDUCTION_A: 100.0,
            COST: 600.0,
            ADMIN: 150.0,
            RECEIVABLE: 350.0,
        }
        deduction = calc.deduction_transfer(balances, [DEDUCTION_A], SALES, ROUNDING)
        after_deduction = calc.apply(balances, deduction)
        self.assertEqual(after_deduction[SALES], -900.0)

        scope = [SALES, DEDUCTION_A, COST, ADMIN]
        closing = calc.closing(after_deduction, scope, RESULT, RETAINED, ROUNDING)
        final = calc.apply(after_deduction, closing)
        for account_id in scope + [RESULT]:
            self.assertEqual(round(final.get(account_id, 0.0), 2), 0.0)
        self.assertEqual(final[RETAINED], -150.0)
        self.assertEqual(final[RECEIVABLE], 350.0)

        # A second pass finds nothing.
        self.assertEqual(
            tuple(calc.deduction_transfer(final, [DEDUCTION_A], SALES, ROUNDING)), ()
        )
        self.assertEqual(
            tuple(calc.closing(final, scope, RESULT, RETAINED, ROUNDING)), ()
        )

    def test_deduction_then_closing_without_apply(self):
        calc = PeriodClosingCalculator
        balances = {SALES: -1000.0, DEDUCTION_A: 100.0, COST: 600.0}
        deduction = calc.deduction_transfer(balances, [DEDUCTION_A], SALES, ROUNDING)
        after = dict(balances)
        for account_id, amount in deduction:
            after[account_id] = after.get(account_id, 0.0) + amount
        lines = calc.closing(
            after, [SALES, DEDUCTION_A, COST], RESULT, RETAINED, ROUNDING
        )
        self.assertEqual(
            tuple(lines),
            (
                (SALES, 900.0),
                (RESULT, -900.0),
                (COST, -600.0),
                (RESULT, 600.0),
                (RESULT, 300.0),
                (RETAINED, -300.0),
            ),
        )


if __name__ == "__main__":
    unittest.main()
