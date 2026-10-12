# -*- coding: utf-8 -*-
"""VAT declaration tests. No Odoo, no database.

The arithmetic of form 01/GTGT is fixed by law, so every relation it prescribes
is asserted here rather than trusted: this is the only place the correctness of
the form can be pinned down.
"""

import unittest
from datetime import date

from ..core.exceptions import ValidationException
from ..domain.ledger.engine import LedgerEngine
from ..domain.tax.declaration import VatDeclarationEngine
from ..domain.tax.engine import TaxEngine
from ..dto.common import AccountDTO, CompanyDTO, CurrencyDTO
from ..dto.filters import LedgerFilter
from ..dto.ledger import MoveLineDTO
from ..dto.tax import VatDeclarationInputDTO
from .fakes import FakeLedgerRepository
from .test_tax import FakeTaxRepository, _row

VND = CurrencyDTO(id=1, name='VND', rounding=1.0, decimal_places=0)
ACME = CompanyDTO(id=1, name='ACME Furniture', currency=VND)

VAT_IN = AccountDTO(1, '133', 'Thuế GTGT được khấu trừ')
VAT_OUT = AccountDTO(2, '3331', 'Thuế GTGT phải nộp')
RECEIVABLE = AccountDTO(3, '131', 'Phải thu của khách hàng')
CHART = (VAT_IN, VAT_OUT, RECEIVABLE)


def _ledger_line(line_id, account_id, amount, when=date(2026, 2, 1)):
    debit = amount if amount > 0 else 0.0
    credit = -amount if amount < 0 else 0.0
    return MoveLineDTO(
        id=line_id, date=when, account_id=account_id, journal_id=1,
        move_id=line_id, move_name='JE/%s' % line_id, debit=debit,
        credit=credit, balance=amount, company_id=1)


class DeclarationCase(unittest.TestCase):

    tax_rows = ()
    ledger_lines = ()

    def setUp(self):
        tax_engine = TaxEngine(FakeTaxRepository(self.tax_rows))
        ledger_engine = LedgerEngine(FakeLedgerRepository(
            companies=(ACME,), accounts=CHART, lines=self.ledger_lines))
        self.engine = VatDeclarationEngine(tax_engine, ledger_engine)

    def _filter(self):
        return LedgerFilter(date_from=date(2026, 1, 1),
                            date_to=date(2026, 3, 31), company_ids=(1,))

    def _compute(self, **kw):
        return self.engine.compute(self._filter(), **kw)

    def _amount(self, report, code):
        return report.by_code(code).amount


class TestDeclarationArithmetic(DeclarationCase):

    tax_rows = (
        # Bán ra: 10% và 5%
        _row(1, 'AA/26E0001', date(2026, 1, 15), -1000000.0, -100000.0),
        _row(2, 'AA/26E0002', date(2026, 2, 10), -2000000.0, -100000.0, rate=5.0),
        # Mua vào
        _row(10, 'BB/26E0100', date(2026, 1, 5), 800000.0, 80000.0,
             move_type='in_invoice'),
    )
    ledger_lines = (
        _ledger_line(1, VAT_OUT.id, -200000.0),
        _ledger_line(2, RECEIVABLE.id, 200000.0),
    )

    def test_purchases(self):
        report = self._compute()
        self.assertEqual(self._amount(report, '23'), 800000.0)
        self.assertEqual(self._amount(report, '24'), 80000.0)
        self.assertEqual(self._amount(report, '25'), 80000.0)

    def test_sales_split_by_rate(self):
        report = self._compute()
        self.assertEqual(self._amount(report, '30'), 2000000.0)
        self.assertEqual(self._amount(report, '31'), 100000.0)
        self.assertEqual(self._amount(report, '32'), 1000000.0)
        self.assertEqual(self._amount(report, '33'), 100000.0)

    def test_item_27_is_the_sum_of_its_rate_columns(self):
        report = self._compute()
        self.assertEqual(
            self._amount(report, '27'),
            self._amount(report, '29') + self._amount(report, '30')
            + self._amount(report, '32'))

    def test_item_28_is_the_sum_of_its_tax_columns(self):
        report = self._compute()
        self.assertEqual(
            self._amount(report, '28'),
            self._amount(report, '31') + self._amount(report, '33'))

    def test_item_34_and_35(self):
        report = self._compute()
        self.assertEqual(self._amount(report, '34'),
                         self._amount(report, '26') + self._amount(report, '27'))
        self.assertEqual(self._amount(report, '35'), self._amount(report, '28'))

    def test_item_36_is_output_less_deductible(self):
        report = self._compute()
        self.assertEqual(self._amount(report, '36'), 200000.0 - 80000.0)


class TestPayableOrCarriedForward(DeclarationCase):
    """Item 40a and item 41 are the two sides of one number and never both."""

    tax_rows = (
        _row(1, 'AA/1', date(2026, 1, 15), -1000000.0, -100000.0),
        _row(10, 'BB/1', date(2026, 1, 5), 300000.0, 30000.0,
             move_type='in_invoice'),
    )

    def test_tax_payable_when_output_exceeds_input(self):
        report = self._compute()
        self.assertEqual(self._amount(report, '40a'), 70000.0)
        self.assertEqual(self._amount(report, '41'), 0.0)

    def test_credit_carried_forward_when_input_exceeds_output(self):
        report = self._compute(
            inputs=VatDeclarationInputDTO(carried_forward=200000.0))
        self.assertEqual(self._amount(report, '40a'), 0.0)
        self.assertEqual(self._amount(report, '41'), 130000.0)

    def test_adjustments_move_the_result(self):
        report = self._compute(inputs=VatDeclarationInputDTO(
            adjustment_decrease=20000.0, adjustment_increase=5000.0))
        self.assertEqual(self._amount(report, '40a'), 70000.0 + 20000.0 - 5000.0)

    def test_refund_reduces_what_carries_forward(self):
        report = self._compute(inputs=VatDeclarationInputDTO(
            carried_forward=200000.0, refund_claimed=50000.0))
        self.assertEqual(self._amount(report, '41'), 130000.0)
        self.assertEqual(self._amount(report, '43'), 80000.0)

    def test_manual_items_are_flagged_as_such(self):
        report = self._compute()
        self.assertFalse(report.by_code('22').is_computed)
        self.assertTrue(report.by_code('36').is_computed)


class TestReconciliation(DeclarationCase):
    """The check that catches VAT posted by hand.

    A journal entry crediting 3331 directly produces no tax line, so no listing
    row and no indicator. The declaration would look complete and be short by
    exactly that amount.
    """

    tax_rows = (_row(1, 'AA/1', date(2026, 1, 15), -1000000.0, -100000.0),)
    ledger_lines = (
        _ledger_line(1, VAT_OUT.id, -100000.0),
        _ledger_line(2, RECEIVABLE.id, 100000.0),
    )

    def test_matching_declaration_reconciles(self):
        report = self._compute()
        self.assertTrue(report.balance_check.is_balanced)
        self.assertEqual(report.balance_check.right_amount, 100000.0)


class TestHandPostedVatIsCaught(DeclarationCase):

    tax_rows = (_row(1, 'AA/1', date(2026, 1, 15), -1000000.0, -100000.0),)
    ledger_lines = (
        _ledger_line(1, VAT_OUT.id, -100000.0),
        _ledger_line(2, RECEIVABLE.id, 100000.0),
        # Bút toán ghi tay, không sinh dòng thuế nên không lên bảng kê.
        _ledger_line(3, VAT_OUT.id, -30000.0),
        _ledger_line(4, RECEIVABLE.id, 30000.0),
    )

    def test_gap_is_reported(self):
        report = self._compute()
        self.assertFalse(report.balance_check.is_balanced)
        self.assertEqual(report.balance_check.difference, -30000.0)

    def test_gap_equals_what_the_listing_missed(self):
        report = self._compute()
        self.assertEqual(report.balance_check.right_amount, 130000.0)
        self.assertEqual(report.balance_check.left_amount, 100000.0)


class TestValidation(DeclarationCase):

    def test_period_start_is_required(self):
        with self.assertRaises(ValidationException):
            self.engine.compute(
                LedgerFilter(date_to=date(2026, 3, 31), company_ids=(1,)))

    def test_empty_period_produces_a_complete_form(self):
        report = self._compute()
        codes = [line.code for line in report.lines]
        for required in ('23', '24', '25', '27', '28', '36', '40a', '43'):
            self.assertIn(required, codes)
        self.assertEqual(self._amount(report, '36'), 0.0)

    def test_diagnostics_can_be_switched_off(self):
        report = self._compute(with_diagnostics=False)
        self.assertIsNone(report.balance_check)


if __name__ == '__main__':
    unittest.main()
