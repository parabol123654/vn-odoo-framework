# -*- coding: utf-8 -*-
"""Cash Flow Engine tests. No Odoo, no database."""

import unittest
from datetime import date

from ..core.exceptions import MappingException, ValidationException
from ..domain.cash_flow.calculators.allocation import CashFlowAllocator
from ..domain.cash_flow.engine import CashFlowEngine
from ..domain.ledger.engine import LedgerEngine
from ..dto.common import AccountDTO, CompanyDTO, CurrencyDTO
from ..dto.filters import LedgerFilter
from ..dto.financial_statement import MappingDTO, MappingLineDTO
from ..dto.ledger import MoveAccountSumDTO, MoveLineDTO
from .fakes import FakeLedgerRepository
from .test_financial_statement import FakeMappingRepository

VND = CurrencyDTO(id=1, name='VND', rounding=1.0, decimal_places=0)
ACME = CompanyDTO(id=1, name='ACME Furniture', currency=VND)

CASH = AccountDTO(1, '1111', 'Tiền mặt')
BANK = AccountDTO(2, '1121', 'Tiền gửi ngân hàng')
RECEIVABLE = AccountDTO(3, '131', 'Phải thu của khách hàng')
PAYABLE = AccountDTO(4, '331', 'Phải trả cho người bán')
REVENUE = AccountDTO(5, '511', 'Doanh thu', include_initial_balance=False)
VAT_OUT = AccountDTO(6, '3331', 'Thuế GTGT phải nộp')
WAGES = AccountDTO(7, '334', 'Phải trả người lao động')
LOAN = AccountDTO(8, '341', 'Vay và nợ thuê tài chính')
ASSET = AccountDTO(9, '211', 'Tài sản cố định hữu hình')
BANK_FEE = AccountDTO(10, '6427', 'Chi phí dịch vụ mua ngoài',
                      include_initial_balance=False)
CHART = (CASH, BANK, RECEIVABLE, PAYABLE, REVENUE, VAT_OUT, WAGES, LOAN,
         ASSET, BANK_FEE)

CASH_IDS = {CASH.id, BANK.id}

MAPPING = MappingDTO(
    code='cf', name='Lưu chuyển tiền tệ', report_type='cash_flow',
    basis='movement', version='TT200', cash_expression='111*,112*',
    lines=(
        MappingLineDTO('01', 'Tiền thu từ bán hàng', sequence=1,
                       expression='131*,511*,3331*'),
        MappingLineDTO('02', 'Tiền chi trả người cung cấp', sequence=2,
                       expression='331*'),
        MappingLineDTO('03', 'Tiền chi trả cho người lao động', sequence=3,
                       expression='334*'),
        MappingLineDTO('20', 'Lưu chuyển thuần từ kinh doanh', sequence=4,
                       formula='01 + 02 + 03', bold=True),
        MappingLineDTO('21', 'Tiền chi mua sắm TSCĐ', sequence=5,
                       expression='211*'),
        MappingLineDTO('30', 'Lưu chuyển thuần từ đầu tư', sequence=6,
                       formula='21', bold=True),
        MappingLineDTO('33', 'Tiền thu từ đi vay', sequence=7,
                       expression='341*', side='debit_only'),
        MappingLineDTO('34', 'Tiền trả nợ gốc vay', sequence=8,
                       expression='341*', side='credit_only'),
        MappingLineDTO('40', 'Lưu chuyển thuần từ tài chính', sequence=9,
                       formula='33 + 34', bold=True),
        MappingLineDTO('50', 'Lưu chuyển tiền thuần trong kỳ', sequence=10,
                       formula='20 + 30 + 40', bold=True),
        MappingLineDTO('60', 'Tiền đầu kỳ', sequence=11,
                       formula='__opening_cash__'),
        MappingLineDTO('70', 'Tiền cuối kỳ', sequence=12,
                       formula='50 + 60', bold=True),
    ))


def _sum(move_id, account_id, debit=0.0, credit=0.0):
    return MoveAccountSumDTO(move_id, account_id, debit, credit)


class TestAllocator(unittest.TestCase):
    """The rule Part 17 §4.3 assumed would need a proportional split."""

    def test_the_non_cash_side_is_the_cash_flow(self):
        rows = (_sum(1, CASH.id, debit=1100.0),
                _sum(1, REVENUE.id, credit=1000.0),
                _sum(1, VAT_OUT.id, credit=100.0))
        result = dict(CashFlowAllocator.attribute(rows, CASH_IDS))
        self.assertEqual(result[REVENUE.id], 1000.0)
        self.assertEqual(result[VAT_OUT.id], 100.0)

    def test_parts_add_back_to_the_cash_movement(self):
        rows = (_sum(1, CASH.id, debit=1100.0),
                _sum(1, REVENUE.id, credit=1000.0),
                _sum(1, VAT_OUT.id, credit=100.0))
        attributed = CashFlowAllocator.attribute(rows, CASH_IDS)
        self.assertEqual(sum(a for _, a in attributed), 1100.0)

    def test_entry_without_cash_is_ignored(self):
        rows = (_sum(1, RECEIVABLE.id, debit=500.0),
                _sum(1, REVENUE.id, credit=500.0))
        self.assertEqual(CashFlowAllocator.attribute(rows, CASH_IDS), ())

    def test_transfer_between_cash_accounts_is_not_a_flow(self):
        rows = (_sum(1, CASH.id, credit=1000.0),
                _sum(1, BANK.id, debit=1000.0))
        self.assertEqual(CashFlowAllocator.attribute(rows, CASH_IDS), ())

    def test_transfer_carrying_a_fee_yields_exactly_the_fee(self):
        rows = (_sum(1, CASH.id, credit=1000.0),
                _sum(1, BANK.id, debit=990.0),
                _sum(1, BANK_FEE.id, debit=10.0))
        result = dict(CashFlowAllocator.attribute(rows, CASH_IDS))
        self.assertEqual(result[BANK_FEE.id], -10.0)

    def test_direction_filter(self):
        self.assertTrue(CashFlowAllocator.keeps(100.0, 'debit_only'))
        self.assertFalse(CashFlowAllocator.keeps(-100.0, 'debit_only'))
        self.assertTrue(CashFlowAllocator.keeps(-100.0, 'credit_only'))
        self.assertTrue(CashFlowAllocator.keeps(-100.0, 'both'))


def _line(line_id, account_id, amount, when, move_id):
    debit = amount if amount > 0 else 0.0
    credit = -amount if amount < 0 else 0.0
    return MoveLineDTO(
        id=line_id, date=when, account_id=account_id, journal_id=1,
        move_id=move_id, move_name='JE/%s' % move_id, debit=debit,
        credit=credit, balance=amount, company_id=1)


class CashFlowCase(unittest.TestCase):

    lines = ()

    def setUp(self):
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART,
                                    lines=self.lines)
        self.engine = CashFlowEngine(LedgerEngine(repo),
                                     FakeMappingRepository([MAPPING]))

    def _filter(self, date_from=date(2026, 1, 1), date_to=date(2026, 12, 31)):
        return LedgerFilter(date_from=date_from, date_to=date_to,
                            company_ids=(1,))

    def _amount(self, report, code):
        return report.by_code(code).amount


class TestDirectMethod(CashFlowCase):

    lines = (
        # Thu tiền bán hàng: 1111 nợ 1100 / 511 có 1000 / 3331 có 100
        _line(1, CASH.id, 1100.0, date(2026, 2, 1), 1),
        _line(2, REVENUE.id, -1000.0, date(2026, 2, 1), 1),
        _line(3, VAT_OUT.id, -100.0, date(2026, 2, 1), 1),
        # Trả tiền nhà cung cấp
        _line(4, PAYABLE.id, 400.0, date(2026, 3, 1), 2),
        _line(5, BANK.id, -400.0, date(2026, 3, 1), 2),
        # Trả lương
        _line(6, WAGES.id, 300.0, date(2026, 4, 1), 3),
        _line(7, CASH.id, -300.0, date(2026, 4, 1), 3),
        # Mua tài sản cố định
        _line(8, ASSET.id, 500.0, date(2026, 5, 1), 4),
        _line(9, BANK.id, -500.0, date(2026, 5, 1), 4),
    )

    def test_inflow_from_sales(self):
        report = self.engine.compute(self._filter(), 'cf')
        self.assertEqual(self._amount(report, '01'), 1100.0)

    def test_outflows_are_negative(self):
        report = self.engine.compute(self._filter(), 'cf')
        self.assertEqual(self._amount(report, '02'), -400.0)
        self.assertEqual(self._amount(report, '03'), -300.0)
        self.assertEqual(self._amount(report, '21'), -500.0)

    def test_subtotals(self):
        report = self.engine.compute(self._filter(), 'cf')
        self.assertEqual(self._amount(report, '20'), 400.0)
        self.assertEqual(self._amount(report, '30'), -500.0)
        self.assertEqual(self._amount(report, '50'), -100.0)

    def test_closing_reconciles_to_the_cash_accounts(self):
        """The check that makes a cash flow statement trustworthy."""
        report = self.engine.compute(self._filter(), 'cf')
        self.assertTrue(report.balance_check.is_balanced)
        self.assertEqual(self._amount(report, '70'),
                         report.balance_check.right_amount)

    def test_nothing_is_unmapped(self):
        report = self.engine.compute(self._filter(), 'cf')
        self.assertEqual(report.unmapped, ())


class TestLoanDirection(CashFlowCase):
    """Drawing and repaying a loan both post to 341; direction separates them."""

    lines = (
        _line(1, BANK.id, 5000.0, date(2026, 2, 1), 1),
        _line(2, LOAN.id, -5000.0, date(2026, 2, 1), 1),
        _line(3, LOAN.id, 2000.0, date(2026, 6, 1), 2),
        _line(4, BANK.id, -2000.0, date(2026, 6, 1), 2),
    )

    def test_borrowing_and_repayment_split(self):
        report = self.engine.compute(self._filter(), 'cf')
        self.assertEqual(self._amount(report, '33'), 5000.0)
        self.assertEqual(self._amount(report, '34'), -2000.0)
        self.assertEqual(self._amount(report, '40'), 3000.0)

    def test_still_reconciles(self):
        report = self.engine.compute(self._filter(), 'cf')
        self.assertTrue(report.balance_check.is_balanced)


class TestUnmappedCounterpart(CashFlowCase):
    """An unmapped counterpart breaks the reconciliation, and says so."""

    lines = (
        _line(1, CASH.id, -700.0, date(2026, 3, 1), 1),
        _line(2, BANK_FEE.id, 700.0, date(2026, 3, 1), 1),
    )

    def test_the_account_is_named(self):
        report = self.engine.compute(self._filter(), 'cf')
        self.assertEqual([a.code for a in report.unmapped], ['6427'])
        self.assertEqual(report.unmapped[0].balance, -700.0)

    def test_reconciliation_fails_by_exactly_that_amount(self):
        report = self.engine.compute(self._filter(), 'cf')
        self.assertFalse(report.balance_check.is_balanced)
        self.assertEqual(report.balance_check.difference, 700.0)


class TestOpeningCash(CashFlowCase):

    lines = (
        _line(1, CASH.id, 2000.0, date(2025, 6, 1), 1),
        _line(2, REVENUE.id, -2000.0, date(2025, 6, 1), 1),
        _line(3, CASH.id, 500.0, date(2026, 2, 1), 2),
        _line(4, REVENUE.id, -500.0, date(2026, 2, 1), 2),
    )

    def test_opening_cash_is_injected(self):
        report = self.engine.compute(self._filter(), 'cf')
        self.assertEqual(self._amount(report, '60'), 2000.0)

    def test_closing_is_opening_plus_the_period(self):
        report = self.engine.compute(self._filter(), 'cf')
        self.assertEqual(self._amount(report, '70'), 2500.0)
        self.assertTrue(report.balance_check.is_balanced)


class TestValidation(CashFlowCase):

    def test_period_start_is_required(self):
        with self.assertRaises(ValidationException):
            self.engine.compute(
                LedgerFilter(date_to=date(2026, 12, 31), company_ids=(1,)),
                'cf')

    def test_unknown_mapping(self):
        with self.assertRaises(MappingException):
            self.engine.compute(self._filter(), 'nope')

    def test_cash_expression_matching_nothing_is_rejected(self):
        mapping = MAPPING._replace(cash_expression='999*')
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART, lines=())
        engine = CashFlowEngine(LedgerEngine(repo),
                                FakeMappingRepository([mapping]))
        with self.assertRaises(MappingException):
            engine.compute(self._filter(), 'cf')


if __name__ == '__main__':
    unittest.main()
