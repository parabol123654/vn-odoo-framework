# -*- coding: utf-8 -*-
"""Calculator unit tests. No Odoo, no database, no fixtures."""

import unittest
from datetime import date

from ..core.utils.dates import fiscal_year_end, fiscal_year_start
from ..core.utils.number import is_zero, round_amount
from ..domain.ledger.calculators.closing_balance import ClosingBalanceCalculator
from ..domain.ledger.calculators.counterpart import CounterpartCalculator
from ..domain.ledger.calculators.opening_balance import OpeningBalanceCalculator
from ..domain.ledger.calculators.running_balance import RunningBalanceCalculator
from ..domain.ledger.calculators.sided_balance import SidedBalanceCalculator
from ..dto.common import AccountDTO, CompanyDTO, CurrencyDTO
from ..dto.ledger import BalanceDTO, MoveAccountSumDTO, MoveLineDTO

VND = CurrencyDTO(id=1, name='VND', rounding=1.0, decimal_places=0)
USD = CurrencyDTO(id=2, name='USD', rounding=0.01, decimal_places=2)


def _line(line_id, account_id, debit=0.0, credit=0.0, move_id=1,
          when=date(2026, 1, 1)):
    return MoveLineDTO(
        id=line_id, date=when, account_id=account_id, journal_id=1,
        move_id=move_id, move_name='JE/%s' % move_id, debit=debit,
        credit=credit, balance=debit - credit, company_id=1)


class TestNumber(unittest.TestCase):

    def test_vnd_rounds_to_whole_dong(self):
        self.assertEqual(round_amount(1234.4, VND.rounding), 1234.0)
        self.assertEqual(round_amount(1234.5, VND.rounding), 1235.0)

    def test_halves_round_away_from_zero(self):
        self.assertEqual(round_amount(-1234.5, VND.rounding), -1235.0)

    def test_binary_representation_does_not_leak(self):
        self.assertEqual(round_amount(0.1 + 0.2, USD.rounding), 0.3)

    def test_is_zero_respects_precision(self):
        self.assertTrue(is_zero(0.4, VND.rounding))
        self.assertFalse(is_zero(0.4, USD.rounding))


class TestFiscalYear(unittest.TestCase):

    def test_calendar_year(self):
        self.assertEqual(fiscal_year_start(date(2026, 6, 15), 31, 12),
                         date(2026, 1, 1))
        self.assertEqual(fiscal_year_end(date(2026, 6, 15), 31, 12),
                         date(2026, 12, 31))

    def test_year_ending_in_march(self):
        """A 31/03 year end puts April..December in the *next* fiscal year."""
        self.assertEqual(fiscal_year_start(date(2026, 6, 15), 31, 3),
                         date(2026, 4, 1))
        self.assertEqual(fiscal_year_end(date(2026, 6, 15), 31, 3),
                         date(2027, 3, 31))
        self.assertEqual(fiscal_year_start(date(2026, 2, 15), 31, 3),
                         date(2025, 4, 1))

    def test_day_is_clamped_to_month_length(self):
        self.assertEqual(fiscal_year_end(date(2026, 1, 1), 31, 2),
                         date(2026, 2, 28))


class TestOpeningWindows(unittest.TestCase):

    def setUp(self):
        self.company = CompanyDTO(id=1, name='ACME', currency=VND)
        self.accounts = (
            AccountDTO(1, '131', 'Phải thu khách hàng',
                       include_initial_balance=True),
            AccountDTO(2, '511', 'Doanh thu bán hàng',
                       include_initial_balance=False),
        )

    def test_no_opening_when_from_inception(self):
        self.assertEqual(
            OpeningBalanceCalculator.windows((self.company,), self.accounts,
                                             None),
            ())

    def test_two_windows_mid_year(self):
        """Balance-sheet accounts from inception, P&L from the year start."""
        windows = OpeningBalanceCalculator.windows(
            (self.company,), self.accounts, date(2026, 3, 1))
        self.assertEqual(len(windows), 2)

        balance_sheet, profit_loss = windows
        self.assertEqual(balance_sheet.account_ids, (1,))
        self.assertIsNone(balance_sheet.date_from)
        self.assertEqual(balance_sheet.date_to, date(2026, 2, 28))

        self.assertEqual(profit_loss.account_ids, (2,))
        self.assertEqual(profit_loss.date_from, date(2026, 1, 1))
        self.assertEqual(profit_loss.date_to, date(2026, 2, 28))

    def test_pl_window_dropped_at_fiscal_year_start(self):
        """On 1 January there is no prior-period P&L to open with."""
        windows = OpeningBalanceCalculator.windows(
            (self.company,), self.accounts, date(2026, 1, 1))
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0].account_ids, (1,))

    def test_companies_sharing_a_fiscal_year_share_one_query(self):
        other = CompanyDTO(id=2, name='Sub', currency=VND)
        windows = OpeningBalanceCalculator.windows(
            (self.company, other), self.accounts, date(2026, 3, 1))
        profit_loss = windows[1]
        self.assertEqual(profit_loss.company_ids, (1, 2))

    def test_differing_fiscal_years_split_into_separate_queries(self):
        other = CompanyDTO(id=2, name='Sub', currency=VND,
                           fiscalyear_last_day=31, fiscalyear_last_month=3)
        windows = OpeningBalanceCalculator.windows(
            (self.company, other), self.accounts, date(2026, 6, 1))
        pl_windows = [w for w in windows if w.account_ids == (2,)]
        self.assertEqual(len(pl_windows), 2)
        self.assertEqual(
            sorted(w.date_from for w in pl_windows),
            [date(2026, 1, 1), date(2026, 4, 1)])

    def test_merge_sums_overlapping_windows(self):
        merged = OpeningBalanceCalculator.merge([
            {(1,): BalanceDTO(100.0, 0.0, 100.0)},
            {(1,): BalanceDTO(50.0, 20.0, 30.0), (2,): BalanceDTO(0.0, 5.0, -5.0)},
        ])
        self.assertEqual(merged[(1,)], BalanceDTO(150.0, 20.0, 130.0))
        self.assertEqual(merged[(2,)].balance, -5.0)


class TestRunningBalance(unittest.TestCase):

    def test_accumulates_from_opening(self):
        lines = (_line(1, 1, debit=100.0), _line(2, 1, credit=30.0),
                 _line(3, 1, debit=5.0))
        self.assertEqual(
            RunningBalanceCalculator.apply(1000.0, lines, VND.rounding),
            (1100.0, 1070.0, 1075.0))

    def test_does_not_drift_on_long_ledgers(self):
        """Accumulate unrounded, round only what is emitted."""
        lines = tuple(_line(i, 1, debit=0.4) for i in range(10))
        result = RunningBalanceCalculator.apply(0.0, lines, VND.rounding)
        self.assertEqual(result[-1], 4.0)

    def test_empty_ledger(self):
        self.assertEqual(RunningBalanceCalculator.apply(0.0, (), VND.rounding),
                         ())


class TestSidedAndClosing(unittest.TestCase):

    def test_debit_balance(self):
        sided = SidedBalanceCalculator.split(1500.0, VND.rounding)
        self.assertEqual((sided.debit_balance, sided.credit_balance),
                         (1500.0, 0.0))

    def test_credit_balance(self):
        sided = SidedBalanceCalculator.split(-800.0, VND.rounding)
        self.assertEqual((sided.debit_balance, sided.credit_balance),
                         (0.0, 800.0))

    def test_zero_shows_on_neither_side(self):
        sided = SidedBalanceCalculator.split(0.0, VND.rounding)
        self.assertEqual((sided.debit_balance, sided.credit_balance), (0.0, 0.0))

    def test_closing_formula(self):
        movement = BalanceDTO(debit=500.0, credit=200.0, balance=300.0)
        self.assertEqual(
            ClosingBalanceCalculator.compute(1000.0, movement, VND.rounding),
            1300.0)


class TestCounterpart(unittest.TestCase):

    def test_two_line_entry(self):
        sums = (MoveAccountSumDTO(1, 111, 1100.0, 0.0),
                MoveAccountSumDTO(1, 511, 0.0, 1100.0))
        index = CounterpartCalculator.index(sums)
        cash = _line(1, 111, debit=1100.0)
        self.assertEqual(CounterpartCalculator.for_line(cash, index), (511,))

    def test_vat_entry_returns_both_credit_accounts(self):
        sums = (MoveAccountSumDTO(1, 111, 1100.0, 0.0),
                MoveAccountSumDTO(1, 511, 0.0, 1000.0),
                MoveAccountSumDTO(1, 3331, 0.0, 100.0))
        index = CounterpartCalculator.index(sums)
        cash = _line(1, 111, debit=1100.0)
        self.assertEqual(CounterpartCalculator.for_line(cash, index),
                         (511, 3331))
        revenue = _line(2, 511, credit=1000.0)
        self.assertEqual(CounterpartCalculator.for_line(revenue, index), (111,))

    def test_account_appearing_on_both_sides_is_excluded_from_itself(self):
        sums = (MoveAccountSumDTO(1, 111, 500.0, 0.0),
                MoveAccountSumDTO(1, 112, 0.0, 500.0))
        index = CounterpartCalculator.index(sums)
        line = _line(1, 111, debit=500.0)
        self.assertNotIn(111, CounterpartCalculator.for_line(line, index))

    def test_unknown_move_yields_nothing(self):
        self.assertEqual(
            CounterpartCalculator.for_line(_line(1, 111, debit=1.0), {}), ())


if __name__ == '__main__':
    unittest.main()
