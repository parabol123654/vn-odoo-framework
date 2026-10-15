# -*- coding: utf-8 -*-
"""Notes to the financial statements (B09): table figures. No Odoo.

Every expected figure below is worked out by hand from the journal items in
``JOURNAL``, not read back from the code.
"""

import unittest
from datetime import date

from ..core.exceptions import MappingException
from ..domain.financial_statement.engine import FinancialStatementEngine
from ..domain.financial_statement.notes import NotesCalculator
from ..domain.ledger.engine import LedgerEngine
from ..dto.filters import LedgerFilter
from ..dto.notes import NoteRowDTO, NoteRowValueDTO, NoteTableDTO
from .fakes import FakeLedgerRepository
from .test_financial_statement import ACME, FakeMappingRepository, _account, _line

CHART = (
    _account(1, '1111', 'Tiền mặt'),
    _account(2, '2111', 'TSCĐ hữu hình'),
    _account(3, '2141', 'Hao mòn TSCĐ hữu hình'),
    _account(4, '33311', 'Thuế GTGT đầu ra'),
    _account(5, '5111', 'Doanh thu bán hàng hóa', bs=False),
    _account(6, '642', 'Chi phí quản lý kinh doanh', bs=False),
    _account(7, '811', 'Chi phí khác', bs=False),
    _account(8, '911', 'Xác định kết quả kinh doanh', bs=False),
    _account(9, '331', 'Phải trả người bán'),
)

PREVIOUS_YEAR = date(2025, 6, 30)
THIS_YEAR = date(2026, 6, 30)

JOURNAL = (
    # 2025: buy an asset for 1 000 cash, depreciate 100, sell 400, VAT 30.
    _line(1, 2, 1000.0, PREVIOUS_YEAR, move_id=1),
    _line(2, 1, -1000.0, PREVIOUS_YEAR, move_id=1),
    _line(3, 6, 100.0, PREVIOUS_YEAR, move_id=2),
    _line(4, 3, -100.0, PREVIOUS_YEAR, move_id=2),
    _line(5, 1, 430.0, PREVIOUS_YEAR, move_id=3),
    _line(6, 5, -400.0, PREVIOUS_YEAR, move_id=3),
    _line(7, 4, -30.0, PREVIOUS_YEAR, move_id=3),
    # 2026: buy another asset for 500 on credit.
    _line(10, 2, 500.0, THIS_YEAR, move_id=10),
    _line(11, 9, -500.0, THIS_YEAR, move_id=10),
    # Dispose of an asset costing 200 with 50 depreciated: loss of 150.
    _line(12, 3, 50.0, THIS_YEAR, move_id=11),
    _line(13, 7, 150.0, THIS_YEAR, move_id=11),
    _line(14, 2, -200.0, THIS_YEAR, move_id=11),
    # Depreciation of the year: 120.
    _line(15, 6, 120.0, THIS_YEAR, move_id=12),
    _line(16, 3, -120.0, THIS_YEAR, move_id=12),
    # Sales of 1 000 plus 80 VAT, cash.
    _line(17, 1, 1080.0, THIS_YEAR, move_id=13),
    _line(18, 5, -1000.0, THIS_YEAR, move_id=13),
    _line(19, 4, -80.0, THIS_YEAR, move_id=13),
    # A sales return of 100 (no VAT, to keep the arithmetic short).
    _line(20, 5, 100.0, THIS_YEAR, move_id=14),
    _line(21, 1, -100.0, THIS_YEAR, move_id=14),
    # VAT paid: 70.
    _line(22, 4, 70.0, THIS_YEAR, move_id=15),
    _line(23, 1, -70.0, THIS_YEAR, move_id=15),
    # Year-end transfer of revenue to 911: must not touch a 'period' table.
    _line(24, 5, 900.0, date(2026, 12, 31), move_id=16),
    _line(25, 8, -900.0, date(2026, 12, 31), move_id=16),
)

YEAR = LedgerFilter(date_from=date(2026, 1, 1), date_to=date(2026, 12, 31),
                    company_ids=(1,))
LAST_YEAR = YEAR.replace(date_from=date(2025, 1, 1),
                         date_to=date(2025, 12, 31))

FIXED_ASSETS = NoteTableDTO(
    code='V5', layout='movement', rows=(
        NoteRowDTO('cost', expression='2111*', sign=1),
        NoteRowDTO('depr', expression='2141*', sign=-1),
        NoteRowDTO('net', formula='cost - depr'),
    ))

TAXES = NoteTableDTO(
    code='V10', layout='movement', rows=(
        NoteRowDTO('vat', expression='3331*', sign=-1),
        NoteRowDTO('other', expression=''),          # filled in by hand
        NoteRowDTO('total', formula='vat + other'),
    ))

CASH = NoteTableDTO(
    code='V1', layout='balance', rows=(
        NoteRowDTO('cash', expression='111*'),
        NoteRowDTO('total', formula='cash'),
    ))

REVENUE = NoteTableDTO(
    code='VI1', layout='period', closing_expression='911*', rows=(
        NoteRowDTO('gross', expression='511*', sign=-1, movement_side='credit'),
        NoteRowDTO('net', expression='511*', sign=-1),
    ))


class _Base(unittest.TestCase):

    def setUp(self):
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART,
                                    lines=JOURNAL)
        engine = FinancialStatementEngine(LedgerEngine(repo),
                                          FakeMappingRepository([]))
        self.calc = NotesCalculator(engine)

    def _all(self, table, previous=None, manual=None):
        values = self.calc.compute(table, YEAR, previous)
        values.update(manual or {})
        return NotesCalculator.apply_formulas(table, values, rounding=1.0)


class TestMovementTable(_Base):

    def test_asset_cost_opening_increase_decrease_closing(self):
        row = self._all(FIXED_ASSETS)['cost']
        self.assertEqual((row.opening, row.increase, row.decrease, row.current),
                         (1000.0, 500.0, 200.0, 1300.0))

    def test_depreciation_grows_on_the_credit_side(self):
        """A credit-natured row (sign -1): credits increase it, debits
        (the disposal) decrease it, and its balance reads positive."""
        row = self._all(FIXED_ASSETS)['depr']
        self.assertEqual((row.opening, row.increase, row.decrease, row.current),
                         (100.0, 120.0, 50.0, 170.0))

    def test_carrying_amount_swaps_sides_of_a_subtracted_term(self):
        """Giá trị còn lại = Nguyên giá − Hao mòn: depreciation decreases it.

        Opening 1000 − 100 = 900; increase = 500 bought + 50 depreciation
        written back on disposal = 550; decrease = 200 disposed + 120
        depreciation = 320; closing 900 + 550 − 320 = 1300 − 170 = 1130.
        """
        row = self._all(FIXED_ASSETS)['net']
        self.assertEqual((row.opening, row.increase, row.decrease, row.current),
                         (900.0, 550.0, 320.0, 1130.0))

    def test_tax_payable_and_paid(self):
        """V.10: opening 30, payable 80, paid 70, closing 40."""
        row = self._all(TAXES)['vat']
        self.assertEqual((row.opening, row.increase, row.decrease, row.current),
                         (30.0, 80.0, 70.0, 40.0))

    def test_hand_filled_row_enters_the_total(self):
        manual = {'other': NoteRowValueDTO('other', current=5.0, opening=2.0,
                                           increase=4.0, decrease=1.0)}
        row = self._all(TAXES, manual=manual)['total']
        self.assertEqual((row.opening, row.increase, row.decrease, row.current),
                         (32.0, 84.0, 71.0, 45.0))

    def test_hand_filled_row_is_not_read_from_the_ledger(self):
        self.assertNotIn('other', self.calc.compute(TAXES, YEAR))


class TestBalanceTable(_Base):

    def test_closing_and_opening(self):
        """Cash: 2025 −1000 + 430 = −570; 2026 adds 1080 − 100 − 70 = 910."""
        row = self._all(CASH)['cash']
        self.assertEqual((row.opening, row.current), (-570.0, 340.0))
        self.assertIsNone(row.increase)

    def test_total(self):
        self.assertEqual(self._all(CASH)['total'].current, 340.0)


class TestPeriodTable(_Base):

    def test_credit_side_is_gross_revenue(self):
        """B02 item 01 style: the credit movement, return not netted."""
        row = self._all(REVENUE, previous=LAST_YEAR)['gross']
        self.assertEqual((row.current, row.opening), (1000.0, 400.0))

    def test_year_end_transfer_is_left_out(self):
        """Net revenue 1000 − 100 = 900, not 0 after the transfer to 911."""
        row = self._all(REVENUE, previous=LAST_YEAR)['net']
        self.assertEqual(row.current, 900.0)

    def test_no_previous_year_means_no_comparative(self):
        self.assertIsNone(self._all(REVENUE)['net'].opening)


class TestValidation(_Base):

    def test_unknown_layout(self):
        with self.assertRaises(MappingException):
            self.calc.compute(NoteTableDTO('x', 'sideways'), YEAR)

    def test_duplicate_row_code(self):
        table = NoteTableDTO('x', 'balance', rows=(
            NoteRowDTO('a', expression='111*'),
            NoteRowDTO('a', expression='112*')))
        with self.assertRaises(MappingException):
            self.calc.compute(table, YEAR)

    def test_expression_and_formula(self):
        table = NoteTableDTO('x', 'balance', rows=(
            NoteRowDTO('a', expression='111*', formula='b'),))
        with self.assertRaises(MappingException):
            self.calc.compute(table, YEAR)

    def test_formula_cycle(self):
        table = NoteTableDTO('x', 'balance', rows=(
            NoteRowDTO('a', formula='b'), NoteRowDTO('b', formula='a')))
        with self.assertRaises(MappingException):
            self.calc.compute(table, YEAR)


#: TT99 V.9 style: one table whose rows are the opening balance, the year's
#: purchases and disposals, the depreciation charge and the closing balance.
ASSET_MATRIX = NoteTableDTO(
    code='V9', layout='balance', rows=(
        NoteRowDTO('open', expression='2111*', figure='opening'),
        NoteRowDTO('bought', expression='2111*', figure='debit'),
        NoteRowDTO('sold', expression='2111*', sign=-1, figure='credit'),
        NoteRowDTO('close', expression='2111*'),
        NoteRowDTO('rolled', formula='open + bought - sold'),
        NoteRowDTO('charge', expression='2141*', sign=-1, figure='credit'),
    ))


class TestRowFigures(_Base):

    def test_each_row_reads_its_own_figure(self):
        """Cost: 1,000 at the start, 500 bought, 200 disposed, 1,300 at the
        end; 120 depreciation charged."""
        values = self._all(ASSET_MATRIX, previous=LAST_YEAR)
        self.assertEqual(
            [values[c].current for c in ('open', 'bought', 'sold', 'close',
                                         'charge')],
            [1000.0, 500.0, 200.0, 1300.0, 120.0])

    def test_rows_reconcile(self):
        values = self._all(ASSET_MATRIX, previous=LAST_YEAR)
        self.assertEqual(values['rolled'].current, values['close'].current)

    def test_comparative_is_the_same_figure_a_year_earlier(self):
        """2025: opening 0, bought 1,000, nothing disposed, closing 1,000,
        depreciation 100."""
        values = self._all(ASSET_MATRIX, previous=LAST_YEAR)
        self.assertEqual(
            [values[c].opening for c in ('open', 'bought', 'sold', 'close',
                                         'charge')],
            [0.0, 1000.0, 0.0, 1000.0, 100.0])

    def test_movement_figures_leave_out_the_year_end_transfer(self):
        """The transfer debits 511 by 900; the debit figure is the return."""
        table = NoteTableDTO('VII2', 'balance', closing_expression='911*',
                             rows=(NoteRowDTO('returns', expression='511*',
                                              figure='debit'),))
        self.assertEqual(self._all(table)['returns'].current, 100.0)

    def test_unknown_figure(self):
        table = NoteTableDTO('x', 'balance', rows=(
            NoteRowDTO('a', expression='111*', figure='sideways'),))
        with self.assertRaises(MappingException):
            self.calc.compute(table, YEAR)
