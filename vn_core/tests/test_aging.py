# -*- coding: utf-8 -*-
"""Aged receivable / payable tests. No Odoo, no database."""

import unittest
from datetime import date

from ..core.enums import AgingBasis, AgingSide
from ..domain.ledger.calculators.aging import AgingCalculator, DEFAULT_BUCKETS
from ..domain.ledger.engine import LedgerEngine
from ..dto.common import AccountDTO, CompanyDTO, CurrencyDTO, PartnerDTO
from ..dto.filters import LedgerFilter
from ..dto.ledger import MoveLineDTO
from .fakes import FakeLedgerRepository

VND = CurrencyDTO(id=1, name='VND', rounding=1.0, decimal_places=0)
ACME = CompanyDTO(id=1, name='ACME Furniture', currency=VND)
RECEIVABLE = AccountDTO(131, '131', 'Phải thu của khách hàng',
                        include_initial_balance=True)
PAYABLE = AccountDTO(331, '331', 'Phải trả cho người bán',
                     include_initial_balance=True)
ACCOUNTS = (RECEIVABLE, PAYABLE)
PARTNERS = (PartnerDTO(7, 'Đại lý Nội thất Hoà Bình'),
            PartnerDTO(8, 'Công ty Gỗ Trường Thành'))


def _open_item(line_id, account_id, amount, doc_date, due_date,
               partner_id=7, residual=None):
    """A single open item; residual defaults to the full amount."""
    debit = amount if amount > 0 else 0.0
    credit = -amount if amount < 0 else 0.0
    return MoveLineDTO(
        id=line_id, date=doc_date, account_id=account_id, journal_id=1,
        move_id=line_id, move_name='INV/%s' % line_id,
        debit=debit, credit=credit, balance=amount,
        partner_id=partner_id, company_id=1, label='Bán hàng',
        date_maturity=due_date,
        amount_residual=amount if residual is None else residual)


class TestBucketIndex(unittest.TestCase):
    """The bucket boundaries must partition the number line exactly."""

    def _index(self, days):
        return AgingCalculator.bucket_index(days, DEFAULT_BUCKETS)

    def test_not_yet_due_goes_to_the_current_column(self):
        self.assertEqual(self._index(-40), 0)
        self.assertEqual(self._index(0), 0)

    def test_boundaries_are_inclusive_and_do_not_overlap(self):
        self.assertEqual(self._index(1), 1)
        self.assertEqual(self._index(30), 1)
        self.assertEqual(self._index(31), 2)
        self.assertEqual(self._index(60), 2)
        self.assertEqual(self._index(61), 3)
        self.assertEqual(self._index(90), 3)
        self.assertEqual(self._index(91), 4)
        self.assertEqual(self._index(180), 4)

    def test_last_bucket_is_open_ended(self):
        self.assertEqual(self._index(181), 5)
        self.assertEqual(self._index(9999), 5)

    def test_every_day_lands_in_exactly_one_bucket(self):
        for days in range(-100, 400):
            index = self._index(days)
            self.assertTrue(0 <= index < len(DEFAULT_BUCKETS),
                            'day %s fell outside the buckets' % days)


class TestDaysOverdue(unittest.TestCase):

    def setUp(self):
        self.line = _open_item(1, 131, 100.0, date(2026, 1, 10),
                               date(2026, 2, 9))

    def test_measured_from_the_due_date(self):
        self.assertEqual(
            AgingCalculator.days_overdue(self.line, date(2026, 3, 11), True), 30)

    def test_measured_from_the_document_date(self):
        self.assertEqual(
            AgingCalculator.days_overdue(self.line, date(2026, 3, 11), False), 60)

    def test_missing_due_date_falls_back_to_the_document_date(self):
        line = self.line._replace(date_maturity=None)
        self.assertEqual(
            AgingCalculator.days_overdue(line, date(2026, 3, 11), True), 60)


class AgingEngineCase(unittest.TestCase):

    lines = ()
    reconciled_after = None

    def setUp(self):
        self.repo = FakeLedgerRepository(
            companies=(ACME,), accounts=ACCOUNTS, lines=self.lines,
            partners=PARTNERS, reconciled_after=self.reconciled_after)
        self.engine = LedgerEngine(self.repo)

    def _filter(self, date_to, **kw):
        return LedgerFilter(date_to=date_to, company_ids=(1,), **kw)

    def _group(self, report, partner_id):
        return next(g for g in report.groups if g.partner_id == partner_id)


class TestAgedReceivable(AgingEngineCase):

    lines = (
        _open_item(1, 131, 100.0, date(2026, 1, 5), date(2026, 6, 30)),   # chưa đến hạn
        _open_item(2, 131, 200.0, date(2026, 1, 5), date(2026, 5, 20)),   # quá hạn 21
        _open_item(3, 131, 300.0, date(2025, 9, 1), date(2025, 10, 1)),   # quá hạn 253
        _open_item(4, 131, 50.0, date(2026, 5, 1), date(2026, 5, 25),
                   partner_id=8),
    )

    def test_amounts_land_in_the_right_columns(self):
        report = self.engine.compute_aging(self._filter(date(2026, 6, 10)))
        group = self._group(report, 7)
        # buckets: [trong hạn, 1-30, 31-60, 61-90, 91-180, >180]
        self.assertEqual(group.amounts, (100.0, 200.0, 0.0, 0.0, 0.0, 300.0))
        self.assertEqual(group.total, 600.0)

    def test_totals_add_up_across_partners(self):
        report = self.engine.compute_aging(self._filter(date(2026, 6, 10)))
        self.assertEqual(report.grand_total, 650.0)
        self.assertEqual(sum(report.totals), report.grand_total)

    def test_groups_sorted_by_partner_name(self):
        report = self.engine.compute_aging(self._filter(date(2026, 6, 10)))
        self.assertEqual([g.partner_name for g in report.groups],
                         ['Công ty Gỗ Trường Thành', 'Đại lý Nội thất Hoà Bình'])

    def test_document_date_basis_ages_items_further(self):
        report = self.engine.compute_aging(
            self._filter(date(2026, 6, 10)), basis=AgingBasis.DOCUMENT_DATE)
        group = self._group(report, 7)
        # Cùng bộ chứng từ nhưng tính từ ngày lập nên tuổi nợ lớn hơn.
        self.assertEqual(group.amounts[0], 0.0)
        self.assertEqual(group.total, 600.0)

    def test_period_start_is_ignored(self):
        """An aged balance is as-at, never restricted to a period."""
        narrow = self.engine.compute_aging(
            self._filter(date(2026, 6, 10), date_from=date(2026, 6, 1)))
        wide = self.engine.compute_aging(self._filter(date(2026, 6, 10)))
        self.assertEqual(narrow.grand_total, wide.grand_total)


class TestSettledItems(AgingEngineCase):

    lines = (
        _open_item(1, 131, 500.0, date(2026, 1, 5), date(2026, 2, 5),
                   residual=0.0),
        _open_item(2, 131, 400.0, date(2026, 1, 6), date(2026, 2, 6),
                   residual=150.0),
    )

    def test_fully_settled_items_are_excluded(self):
        report = self.engine.compute_aging(self._filter(date(2026, 6, 10)))
        ids = {l.source.id for g in report.groups for l in g.lines}
        self.assertNotIn(1, ids)

    def test_partly_settled_items_show_only_the_residual(self):
        report = self.engine.compute_aging(self._filter(date(2026, 6, 10)))
        self.assertEqual(self._group(report, 7).total, 150.0)


class TestResidualIsReconstructed(AgingEngineCase):
    """The whole point of the report: age the balance *as it stood*.

    Line 1 shows a zero residual today because it was collected in July, but a
    report dated 10 June must still show it outstanding.
    """

    lines = (
        _open_item(1, 131, 500.0, date(2026, 1, 5), date(2026, 2, 5),
                   residual=0.0),
    )
    reconciled_after = {1: 500.0}

    def test_payments_after_the_reporting_date_are_added_back(self):
        report = self.engine.compute_aging(self._filter(date(2026, 6, 10)))
        self.assertEqual(report.grand_total, 500.0)
        self.assertEqual(self._group(report, 7).amounts[4], 500.0)  # quá hạn 125


class TestAgedPayable(AgingEngineCase):

    lines = (
        _open_item(1, 331, -700.0, date(2026, 4, 1), date(2026, 5, 1)),
        _open_item(2, 131, 250.0, date(2026, 4, 1), date(2026, 5, 1)),
    )

    def test_payables_are_reported_as_positive_amounts(self):
        report = self.engine.compute_aging(
            self._filter(date(2026, 6, 10)), side=AgingSide.PAYABLE)
        self.assertEqual(report.grand_total, 700.0)

    def test_receivable_and_payable_do_not_overlap(self):
        receivable = self.engine.compute_aging(
            self._filter(date(2026, 6, 10)), side=AgingSide.RECEIVABLE)
        payable = self.engine.compute_aging(
            self._filter(date(2026, 6, 10)), side=AgingSide.PAYABLE)
        self.assertEqual(receivable.grand_total, 250.0)
        self.assertEqual(payable.grand_total, 700.0)


class TestEmptyReport(AgingEngineCase):

    def test_no_open_items(self):
        report = self.engine.compute_aging(self._filter(date(2026, 6, 10)))
        self.assertEqual(report.groups, ())
        self.assertEqual(report.grand_total, 0.0)
        self.assertEqual(len(report.totals), len(DEFAULT_BUCKETS))


if __name__ == '__main__':
    unittest.main()
