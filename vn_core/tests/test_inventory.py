# -*- coding: utf-8 -*-
"""Inventory Engine tests. No Odoo, no database."""

import unittest
from datetime import date

from ..core.exceptions import ValidationException
from ..domain.inventory.calculators.running_stock import RunningStockCalculator
from ..domain.inventory.engine import InventoryEngine
from ..domain.inventory.repository import IInventoryRepository
from ..dto.common import CurrencyDTO
from ..dto.filters import InventoryFilter
from ..dto.inventory import InventoryBalanceDTO, InventoryMoveDTO, ProductDTO

VND = CurrencyDTO(id=1, name='VND', rounding=1.0, decimal_places=0)

VAN_MDF = ProductDTO(1, 'NVL001', 'Ván MDF phủ melamine', 'Tấm', 'Nguyên vật liệu')
GO_SOI = ProductDTO(2, 'NVL002', 'Gỗ sồi xẻ sấy', 'm3', 'Nguyên vật liệu')
BAN_AN = ProductDTO(3, 'TP001', 'Bộ bàn ăn gỗ sồi', 'Bộ', 'Thành phẩm')
PRODUCTS = (VAN_MDF, GO_SOI, BAN_AN)


class FakeInventoryRepository(IInventoryRepository):

    def __init__(self, movements=(), opening=None, products=PRODUCTS,
                 currency=VND):
        self.movements = tuple(movements)
        self.opening = dict(opening or {})
        self.products = tuple(products)
        self.currency = currency

    def get_currency(self, company_ids):
        return self.currency

    def get_products(self, inventory_filter):
        if inventory_filter.product_ids:
            return tuple(p for p in self.products
                         if p.id in inventory_filter.product_ids)
        return self.products

    def get_opening(self, inventory_filter):
        if not inventory_filter.date_from:
            return {}
        return dict(self.opening)

    def get_movements(self, inventory_filter):
        return tuple(
            m for m in sorted(self.movements, key=lambda m: (m.date, m.id))
            if (not inventory_filter.date_from
                or m.date >= inventory_filter.date_from)
            and m.date <= inventory_filter.date_to
            and (not inventory_filter.product_ids
                 or m.product_id in inventory_filter.product_ids))


def _move(move_id, product_id, when, quantity, value, reference='PN001'):
    unit = abs(value / quantity) if quantity else 0.0
    return InventoryMoveDTO(
        id=move_id, date=when, product_id=product_id, quantity=quantity,
        value=value, unit_cost=unit, reference=reference,
        description='Nhập kho' if quantity > 0 else 'Xuất kho')


class TestRunningStock(unittest.TestCase):

    def test_incoming_and_outgoing_are_never_both(self):
        incoming, outgoing = RunningStockCalculator.split(
            _move(1, 1, date(2026, 1, 5), 10, 1000000.0), VND.rounding)
        self.assertEqual(incoming.quantity, 10)
        self.assertEqual(outgoing, InventoryBalanceDTO())

    def test_negative_layer_is_an_outgoing_movement(self):
        """A return on a purchase is outgoing, whatever document it sits on."""
        incoming, outgoing = RunningStockCalculator.split(
            _move(1, 1, date(2026, 1, 5), -4, -400000.0), VND.rounding)
        self.assertEqual(incoming, InventoryBalanceDTO())
        self.assertEqual(outgoing.quantity, 4)
        self.assertEqual(outgoing.value, 400000.0)

    def test_running_balance_tracks_quantity_and_value_together(self):
        moves = (_move(1, 1, date(2026, 1, 5), 10, 1000000.0),
                 _move(2, 1, date(2026, 1, 8), -4, -400000.0))
        running = RunningStockCalculator.apply(
            InventoryBalanceDTO(5, 500000.0), moves, VND.rounding)
        self.assertEqual([r.quantity for r in running], [15, 11])
        self.assertEqual([r.value for r in running], [1500000.0, 1100000.0])


class InventoryEngineCase(unittest.TestCase):

    movements = ()
    opening = None

    def setUp(self):
        self.repo = FakeInventoryRepository(self.movements, self.opening)
        self.engine = InventoryEngine(self.repo)

    def _filter(self, date_from=date(2026, 1, 1), date_to=date(2026, 12, 31),
                **kw):
        return InventoryFilter(date_to=date_to, date_from=date_from,
                               company_ids=(1,), **kw)

    def _group(self, report, product_id):
        return next(g for g in report.groups if g.product.id == product_id)


class TestNhapXuatTon(InventoryEngineCase):

    opening = {1: InventoryBalanceDTO(20, 2000000.0)}
    movements = (
        _move(1, 1, date(2026, 2, 10), 30, 3300000.0, 'PN/2026/001'),
        _move(2, 1, date(2026, 3, 5), -25, -2600000.0, 'PX/2026/001'),
        _move(3, 2, date(2026, 3, 8), 12, 9600000.0, 'PN/2026/002'),
    )

    def test_opening_incoming_outgoing_closing(self):
        report = self.engine.compute_summary(self._filter())
        group = self._group(report, 1)
        self.assertEqual(group.opening.quantity, 20)
        self.assertEqual(group.incoming.quantity, 30)
        self.assertEqual(group.outgoing.quantity, 25)
        self.assertEqual(group.closing.quantity, 25)
        self.assertEqual(group.closing.value, 2700000.0)

    def test_closing_equals_opening_plus_in_minus_out(self):
        report = self.engine.compute_summary(self._filter())
        for group in report.groups:
            self.assertAlmostEqual(
                group.closing.value,
                group.opening.value + group.incoming.value - group.outgoing.value,
                places=2)

    def test_summary_carries_no_card_lines(self):
        report = self.engine.compute_summary(self._filter())
        self.assertTrue(all(g.lines == () for g in report.groups))

    def test_products_without_movement_are_dropped(self):
        report = self.engine.compute_summary(self._filter())
        self.assertNotIn(3, [g.product.id for g in report.groups])

    def test_groups_sorted_by_product_code(self):
        report = self.engine.compute_summary(self._filter())
        self.assertEqual([g.product.code for g in report.groups],
                         ['NVL001', 'NVL002'])

    def test_total_value_is_the_sum_of_closing(self):
        report = self.engine.compute_summary(self._filter())
        self.assertEqual(report.totals.value,
                         sum(g.closing.value for g in report.groups))


class TestStockCard(InventoryEngineCase):

    opening = {1: InventoryBalanceDTO(20, 2000000.0)}
    movements = (
        _move(1, 1, date(2026, 2, 10), 30, 3300000.0, 'PN/2026/001'),
        _move(2, 1, date(2026, 3, 5), -25, -2600000.0, 'PX/2026/001'),
    )

    def test_card_lines_carry_a_running_balance(self):
        report = self.engine.compute_stock_card(self._filter())
        lines = self._group(report, 1).lines
        self.assertEqual([l.running.quantity for l in lines], [50, 25])
        self.assertEqual([l.running.value for l in lines],
                         [5300000.0, 2700000.0])

    def test_each_line_is_either_in_or_out(self):
        report = self.engine.compute_stock_card(self._filter())
        lines = self._group(report, 1).lines
        self.assertEqual(lines[0].incoming.quantity, 30)
        self.assertEqual(lines[0].outgoing.quantity, 0)
        self.assertEqual(lines[1].outgoing.quantity, 25)
        self.assertEqual(lines[1].incoming.quantity, 0)

    def test_unit_cost_comes_from_the_layer(self):
        """Never quantity times a current standard price."""
        report = self.engine.compute_stock_card(self._filter())
        self.assertEqual(self._group(report, 1).lines[0].unit_cost, 110000.0)

    def test_product_filter_narrows_the_card(self):
        report = self.engine.compute_stock_card(self._filter(product_ids=(1,)))
        self.assertEqual([g.product.id for g in report.groups], [1])

    def test_counterpart_account_reaches_the_line(self):
        """S10-DN prints "TK đối ứng"; it must survive the trip untouched."""
        move = _move(1, 1, date(2026, 2, 10), 30, 3300000.0)._replace(
            counterpart='331')
        repo = FakeInventoryRepository(movements=(move,), opening=self.opening)
        report = InventoryEngine(repo).compute_stock_card(self._filter())
        self.assertEqual(self._group(report, 1).lines[0].counterpart, '331')


class TestAveragingDifference(InventoryEngineCase):
    """Odoo's moving average against bình quân cuối kỳ.

    Opening 20 units at 100,000. A receipt of 30 at 110,000 makes the period-end
    weighted average 106,000 — but Odoo issued the 25 units at its moving
    average of the moment, so the two methods leave different closing values.
    The engine reports Odoo's figure, because that is what reached the ledger,
    and exposes the period-end average alongside so the gap is visible.
    """

    opening = {1: InventoryBalanceDTO(20, 2000000.0)}
    movements = (
        _move(1, 1, date(2026, 2, 10), 30, 3300000.0),
        _move(2, 1, date(2026, 3, 5), -25, -2600000.0),
    )

    def test_period_end_average_is_exposed(self):
        report = self.engine.compute_summary(self._filter())
        group = self._group(report, 1)
        self.assertEqual(group.average_unit_cost, 106000.0)

    def test_reported_value_follows_the_ledger_not_the_average(self):
        report = self.engine.compute_summary(self._filter())
        group = self._group(report, 1)
        period_end_valuation = group.closing.quantity * group.average_unit_cost
        self.assertEqual(group.closing.value, 2700000.0)
        self.assertNotEqual(group.closing.value, period_end_valuation)

    def test_average_of_nothing_is_zero(self):
        repo = FakeInventoryRepository()
        report = InventoryEngine(repo).compute_summary(self._filter())
        self.assertEqual(report.groups, ())


class TestFromInception(InventoryEngineCase):

    opening = {1: InventoryBalanceDTO(20, 2000000.0)}
    movements = (_move(1, 1, date(2026, 2, 10), 30, 3300000.0),)

    def test_no_start_date_means_no_opening(self):
        report = self.engine.compute_summary(
            self._filter(date_from=None, date_to=date(2026, 12, 31)))
        self.assertEqual(self._group(report, 1).opening.quantity, 0)
        self.assertEqual(self._group(report, 1).closing.quantity, 30)


class TestValidation(InventoryEngineCase):

    def test_no_company(self):
        with self.assertRaises(ValidationException):
            self.engine.compute_summary(
                InventoryFilter(date_to=date(2026, 12, 31), company_ids=()))

    def test_reversed_dates(self):
        with self.assertRaises(ValidationException):
            self.engine.compute_summary(
                self._filter(date(2026, 12, 31), date(2026, 1, 1)))

    def test_empty_period(self):
        report = self.engine.compute_summary(self._filter())
        self.assertEqual(report.groups, ())
        self.assertEqual(report.totals.value, 0.0)


if __name__ == '__main__':
    unittest.main()
