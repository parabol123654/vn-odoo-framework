# -*- coding: utf-8 -*-
"""Fixed Asset Engine tests. No Odoo, no database.

The cast: a machine depreciating since mid-2025 (initial balances for the old
year, posted entries since January), a machine arriving in March, an office
device removed in March, and one asset whose whole schedule is still a plan.
Between them they exercise every rule the engine claims to follow.
"""

import unittest
from datetime import date

from ..core.exceptions import ValidationException
from ..domain.asset.engine import AssetEngine
from ..domain.asset.repository import IAssetRepository
from ..dto.asset import AssetDTO, AssetLineDTO, AssetProfileDTO
from ..dto.common import CurrencyDTO
from ..dto.filters import AssetFilter

VND = CurrencyDTO(id=1, name='VND', rounding=1.0, decimal_places=0)

MACHINES = AssetProfileDTO(1, 'Máy móc, thiết bị', '2112', '2141', '627')
OFFICE = AssetProfileDTO(2, 'Thiết bị quản lý', '2114', '2141', '642')

PRESS = AssetDTO(
    id=1, name='Máy ép gỗ', code='TSCD-001', profile_id=1, state='open',
    purchase_value=240000000.0, date_start=date(2025, 7, 1),
    method='linear', method_number=10, method_period='month',
    acquisition_ref='BB/2025/07')
SAW = AssetDTO(
    id=2, name='Máy cưa CNC', code='TSCD-002', profile_id=1, state='open',
    purchase_value=60000000.0, date_start=date(2026, 3, 10),
    method='linear', method_number=5, method_period='month')
PRINTER = AssetDTO(
    id=3, name='Máy in văn phòng', code='TSCD-003', profile_id=2,
    state='removed', purchase_value=18000000.0,
    date_start=date(2025, 1, 1), date_remove=date(2026, 3, 5),
    method='linear', method_number=3, method_period='month')
PLANNED = AssetDTO(
    id=4, name='Xe nâng (kế hoạch)', code='TSCD-004', profile_id=1,
    state='open', purchase_value=90000000.0, date_start=date(2026, 3, 1),
    method='linear', method_number=5, method_period='month')
GONE_LAST_YEAR = AssetDTO(
    id=5, name='Đã thanh lý 2025', code='TSCD-000', profile_id=2,
    state='removed', purchase_value=5000000.0,
    date_start=date(2024, 1, 1), date_remove=date(2025, 12, 31),
    method='linear', method_number=2, method_period='month')


def _month_end(year, month):
    from calendar import monthrange
    return date(year, month, monthrange(year, month)[1])


def _lines():
    lines, counter = [], [0]

    def add(asset_id, when, amount, expense, posted=True, init=False):
        counter[0] += 1
        lines.append(AssetLineDTO(
            id=counter[0], asset_id=asset_id, date=when, amount=amount,
            posted=posted, init=init, expense_code=expense,
            move_name='KH/%s' % counter[0] if posted else ''))

    # PRESS: init entries Jul-Dec 2025, posted Jan-Aug 2026, 2,000,000/month.
    for month in range(7, 13):
        add(1, _month_end(2025, month), 2000000.0, '627',
            posted=False, init=True)
    for month in range(1, 9):
        add(1, _month_end(2026, month), 2000000.0, '627')
    # SAW: first depreciation at the end of March 2026.
    add(2, _month_end(2026, 3), 1000000.0, '627')
    # PRINTER: posted through February, removed 5 March.
    for month in range(1, 3):
        add(3, _month_end(2026, month), 500000.0, '642')
    # PLANNED: schedule exists, nothing posted.
    for month in range(3, 9):
        add(4, _month_end(2026, month), 1500000.0, '627', posted=False)
    return tuple(lines)


class FakeAssetRepository(IAssetRepository):

    def __init__(self, profiles=(MACHINES, OFFICE),
                 assets=(PRESS, SAW, PRINTER, PLANNED, GONE_LAST_YEAR),
                 lines=None, currency=VND):
        self.profiles = tuple(profiles)
        self.assets = tuple(assets)
        self.lines = _lines() if lines is None else tuple(lines)
        self.currency = currency

    def get_currency(self, company_ids):
        return self.currency

    def get_profiles(self, asset_filter):
        if asset_filter.profile_ids:
            return tuple(p for p in self.profiles
                         if p.id in asset_filter.profile_ids)
        return self.profiles

    def get_assets(self, asset_filter):
        assets = self.assets
        if asset_filter.asset_ids:
            assets = tuple(a for a in assets if a.id in asset_filter.asset_ids)
        if asset_filter.profile_ids:
            assets = tuple(a for a in assets
                           if a.profile_id in asset_filter.profile_ids)
        return assets

    def get_lines(self, asset_ids, date_from=None, date_to=None):
        return tuple(
            line for line in sorted(self.lines, key=lambda l: (l.date, l.id))
            if line.asset_id in tuple(asset_ids)
            and (not date_from or line.date >= date_from)
            and (not date_to or line.date <= date_to))


class AssetEngineCase(unittest.TestCase):

    def setUp(self):
        self.repo = FakeAssetRepository()
        self.engine = AssetEngine(self.repo)

    def _filter(self, **kw):
        kw.setdefault('date_from', date(2026, 1, 1))
        kw.setdefault('date_to', date(2026, 3, 31))
        return AssetFilter(company_ids=(1,), **kw)


class TestRegister(AssetEngineCase):

    def _row(self, report, asset_id):
        for group in report.groups:
            for row in group.rows:
                if row.asset.id == asset_id:
                    return row
        raise AssertionError('asset %s not on the register' % asset_id)

    def test_accumulated_counts_posted_and_initial_balance_lines(self):
        """PRESS: six init months of 2025 plus January–March 2026."""
        row = self._row(self.engine.compute_register(self._filter()), 1)
        self.assertEqual(row.accumulated, 18000000.0)
        self.assertEqual(row.residual, 222000000.0)

    def test_planned_depreciation_stays_out_of_the_books_by_default(self):
        row = self._row(self.engine.compute_register(self._filter()), 4)
        self.assertEqual(row.accumulated, 0.0)

    def test_planned_depreciation_joins_only_when_asked(self):
        row = self._row(self.engine.compute_register(
            self._filter(include_unposted=True)), 4)
        self.assertEqual(row.accumulated, 1500000.0)

    def test_asset_removed_inside_the_period_is_still_on_the_page(self):
        row = self._row(self.engine.compute_register(self._filter()), 3)
        self.assertEqual(row.asset.date_remove, date(2026, 3, 5))

    def test_asset_removed_before_the_period_is_not(self):
        report = self.engine.compute_register(self._filter())
        with self.assertRaises(AssertionError):
            self._row(report, 5)

    def test_grouped_by_profile_with_totals(self):
        report = self.engine.compute_register(self._filter())
        machines = next(g for g in report.groups if g.profile.id == 1)
        self.assertEqual(machines.total_purchase, 390000000.0)
        self.assertEqual(report.total_accumulated,
                         sum(g.total_accumulated for g in report.groups))

    def test_linear_rate_is_derived_and_degressive_stays_blank(self):
        row = self._row(self.engine.compute_register(self._filter()), 1)
        self.assertEqual(row.asset.annual_rate, 10.0)
        degressive = PRESS._replace(method='degressive')
        self.assertEqual(degressive.annual_rate, 0.0)


class TestCards(AssetEngineCase):

    def _card(self, asset_id, **kw):
        report = self.engine.compute_cards(self._filter(**kw))
        return next(c for c in report.cards if c.asset.id == asset_id)

    def test_years_accumulate_across_the_asset_life(self):
        """The card ignores date_from: it is the asset's whole story."""
        card = self._card(1)
        self.assertEqual([(y.year, y.amount, y.cumulative)
                          for y in card.years],
                         [(2025, 12000000.0, 12000000.0),
                          (2026, 6000000.0, 18000000.0)])

    def test_residual_follows_the_recorded_wear(self):
        card = self._card(1)
        self.assertEqual(card.accumulated, 18000000.0)
        self.assertEqual(card.residual, 222000000.0)

    def test_card_carries_its_profile_accounts(self):
        card = self._card(1)
        self.assertEqual(card.profile.asset_account_code, '2112')


class TestAllocation(AssetEngineCase):

    def _march(self, **kw):
        kw.setdefault('date_from', date(2026, 3, 1))
        kw.setdefault('date_to', date(2026, 3, 31))
        return self.engine.compute_allocation(self._filter(**kw))

    def _row(self, report, profile_id):
        return next(r for r in report.rows if r.profile.id == profile_id)

    def test_cells_split_by_the_account_actually_charged(self):
        report = self._march()
        self.assertEqual(report.columns, ('627',))
        self.assertEqual(self._row(report, 1).total, 3000000.0)
        self.assertEqual(report.grand_total, 3000000.0)

    def test_previous_period_is_the_calendar_month_not_thirty_days(self):
        """A day-count window would drag 31 January into "February"."""
        report = self._march()
        self.assertEqual(report.summary.previous_total, 2500000.0)

    def test_increase_is_the_assets_that_started_this_period(self):
        self.assertEqual(self._march().summary.increase, 1000000.0)

    def test_decrease_is_the_assets_that_stopped(self):
        self.assertEqual(self._march().summary.decrease, 500000.0)

    def test_the_summary_balances_when_nothing_else_changed(self):
        self.assertEqual(self._march().summary.imbalance, 0.0)

    def test_planned_lines_join_only_on_request(self):
        report = self._march(include_unposted=True)
        self.assertEqual(report.columns, ('627',))
        self.assertEqual(self._row(report, 1).total, 4500000.0)

    def test_a_period_document_requires_a_start_date(self):
        with self.assertRaises(ValidationException):
            self.engine.compute_allocation(
                AssetFilter(date_to=date(2026, 3, 31), company_ids=(1,)))


class TestValidation(AssetEngineCase):

    def test_no_company(self):
        with self.assertRaises(ValidationException):
            self.engine.compute_register(
                AssetFilter(date_to=date(2026, 12, 31), company_ids=()))

    def test_reversed_dates(self):
        with self.assertRaises(ValidationException):
            self.engine.compute_register(
                self._filter(date_from=date(2027, 1, 1)))


if __name__ == '__main__':
    unittest.main()
