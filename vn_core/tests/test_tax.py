# -*- coding: utf-8 -*-
"""Tax Engine tests. No Odoo, no database."""

import unittest
from datetime import date

from ..core.enums import TaxDirection
from ..core.exceptions import ValidationException
from ..domain.tax.calculators.vat_sign import VatSignCalculator
from ..domain.tax.engine import TaxEngine
from ..domain.tax.repository import ITaxRepository
from ..dto.common import CurrencyDTO
from ..dto.filters import LedgerFilter
from ..dto.tax import TaxLineDTO

VND = CurrencyDTO(id=1, name='VND', rounding=1.0, decimal_places=0)


class FakeTaxRepository(ITaxRepository):
    """In-memory tax rows, stored with raw ledger signs.

    Sales VAT is a credit, so it arrives negative; purchase VAT is a debit and
    arrives positive. Normalising that is the Engine's job, and storing the raw
    signs here is what makes the test meaningful.
    """

    def __init__(self, rows=(), currency=VND):
        self.rows = tuple(rows)
        self.currency = currency
        self.calls = []

    def get_currency(self, company_ids):
        return self.currency

    def get_tax_lines(self, ledger_filter, direction):
        self.calls.append(direction)
        return tuple(r for r in self.rows
                     if r.move_type.startswith('out')
                     == (direction is TaxDirection.SALE))


def _row(move_id, number, when, base, tax, rate=10.0, move_type='out_invoice',
         partner='Đại lý Hoà Bình', vat='0101234567'):
    return TaxLineDTO(
        move_id=move_id, move_name='INV/%s' % move_id, invoice_number=number,
        invoice_date=when, partner_id=7, partner_name=partner, partner_vat=vat,
        tax_id=int(rate), tax_name='%d%% GTGT' % rate, tax_rate=rate,
        base_amount=base, tax_amount=tax, move_type=move_type)


class TestVatSign(unittest.TestCase):

    def test_sale_flips_the_credit_balance(self):
        self.assertEqual(
            VatSignCalculator.normalise(-100.0, TaxDirection.SALE), 100.0)

    def test_purchase_keeps_the_debit_balance(self):
        self.assertEqual(
            VatSignCalculator.normalise(100.0, TaxDirection.PURCHASE), 100.0)


class TaxEngineCase(unittest.TestCase):

    rows = ()

    def setUp(self):
        self.repo = FakeTaxRepository(self.rows)
        self.engine = TaxEngine(self.repo)

    def _filter(self, date_from=date(2026, 1, 1), date_to=date(2026, 3, 31)):
        return LedgerFilter(date_from=date_from, date_to=date_to,
                            company_ids=(1,))

    def _group(self, report, rate):
        return next(g for g in report.groups if g.rate == rate)


class TestVatSales(TaxEngineCase):

    rows = (
        # Ledger signs: output VAT is a credit, so base and tax are negative.
        _row(1, 'AA/26E0001', date(2026, 1, 15), -1000000.0, -100000.0),
        _row(2, 'AA/26E0002', date(2026, 2, 10), -500000.0, -50000.0),
        _row(3, 'AA/26E0003', date(2026, 2, 20), -2000000.0, -100000.0, rate=5.0),
        _row(4, 'AA/26E0004', date(2026, 3, 1), -300000.0, 0.0, rate=0.0),
    )

    def test_amounts_come_out_positive(self):
        report = self.engine.compute_vat_listing(
            self._filter(), TaxDirection.SALE)
        self.assertEqual(report.base_total, 3800000.0)
        self.assertEqual(report.tax_total, 250000.0)

    def test_grouped_by_rate_ascending(self):
        report = self.engine.compute_vat_listing(
            self._filter(), TaxDirection.SALE)
        self.assertEqual([g.rate for g in report.groups], [0.0, 5.0, 10.0])

    def test_group_totals(self):
        report = self.engine.compute_vat_listing(
            self._filter(), TaxDirection.SALE)
        ten = self._group(report, 10.0)
        self.assertEqual(ten.base_total, 1500000.0)
        self.assertEqual(ten.tax_total, 150000.0)

    def test_rate_labels(self):
        report = self.engine.compute_vat_listing(
            self._filter(), TaxDirection.SALE)
        self.assertEqual(self._group(report, 10.0).label, 'Thuế suất 10%')
        self.assertEqual(self._group(report, 0.0).label,
                         'Thuế suất 0% hoặc không chịu thuế')

    def test_invoice_count_is_distinct(self):
        report = self.engine.compute_vat_listing(
            self._filter(), TaxDirection.SALE)
        self.assertEqual(report.invoice_count, 4)

    def test_lines_ordered_by_date_then_number(self):
        report = self.engine.compute_vat_listing(
            self._filter(), TaxDirection.SALE)
        ten = self._group(report, 10.0)
        self.assertEqual([l.invoice_number for l in ten.lines],
                         ['AA/26E0001', 'AA/26E0002'])

    def test_partner_tax_code_is_carried(self):
        report = self.engine.compute_vat_listing(
            self._filter(), TaxDirection.SALE)
        self.assertEqual(self._group(report, 10.0).lines[0].partner_vat,
                         '0101234567')


class TestCreditNotes(TaxEngineCase):
    """A credit note reverses the entry, so it must reduce the declaration."""

    rows = (
        _row(1, 'AA/26E0001', date(2026, 1, 15), -1000000.0, -100000.0),
        _row(2, 'AA/26E0009', date(2026, 1, 20), 200000.0, 20000.0,
             move_type='out_refund'),
    )

    def test_refund_is_negative_without_a_special_case(self):
        report = self.engine.compute_vat_listing(
            self._filter(), TaxDirection.SALE)
        self.assertEqual(report.tax_total, 80000.0)
        self.assertEqual(report.base_total, 800000.0)

    def test_refund_line_is_flagged(self):
        report = self.engine.compute_vat_listing(
            self._filter(), TaxDirection.SALE)
        refunds = [l for g in report.groups for l in g.lines if l.is_refund]
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds[0].tax_amount, -20000.0)


class TestVatPurchase(TaxEngineCase):

    rows = (
        # Input VAT is a debit, so it already arrives positive.
        _row(10, 'BB/26E0100', date(2026, 1, 5), 800000.0, 80000.0,
             move_type='in_invoice', partner='Gỗ Trường Thành'),
        _row(11, 'BB/26E0101', date(2026, 2, 5), 400000.0, 40000.0,
             move_type='in_invoice', partner='An Cường'),
    )

    def test_purchase_amounts_stay_positive(self):
        report = self.engine.compute_vat_listing(
            self._filter(), TaxDirection.PURCHASE)
        self.assertEqual(report.base_total, 1200000.0)
        self.assertEqual(report.tax_total, 120000.0)

    def test_sales_and_purchase_do_not_mix(self):
        sales = self.engine.compute_vat_listing(
            self._filter(), TaxDirection.SALE)
        self.assertEqual(sales.groups, ())
        self.assertEqual(sales.tax_total, 0.0)

    def test_direction_reaches_the_repository(self):
        self.engine.compute_vat_listing(self._filter(), TaxDirection.PURCHASE)
        self.assertEqual(self.repo.calls, [TaxDirection.PURCHASE])


class TestFractionalRate(TaxEngineCase):

    rows = (_row(1, 'AA/1', date(2026, 1, 5), -1000.0, -85.0, rate=8.5),)

    def test_label_keeps_the_decimal(self):
        report = self.engine.compute_vat_listing(
            self._filter(), TaxDirection.SALE)
        self.assertEqual(report.groups[0].label, 'Thuế suất 8.5%')


class TestValidation(TaxEngineCase):

    def test_no_company(self):
        with self.assertRaises(ValidationException):
            self.engine.compute_vat_listing(
                LedgerFilter(date_to=date(2026, 3, 31), company_ids=()),
                TaxDirection.SALE)

    def test_reversed_dates(self):
        with self.assertRaises(ValidationException):
            self.engine.compute_vat_listing(
                self._filter(date(2026, 3, 31), date(2026, 1, 1)),
                TaxDirection.SALE)

    def test_empty_period(self):
        report = self.engine.compute_vat_listing(
            self._filter(), TaxDirection.SALE)
        self.assertEqual(report.groups, ())
        self.assertEqual(report.invoice_count, 0)
        self.assertEqual(report.tax_total, 0.0)


if __name__ == '__main__':
    unittest.main()
