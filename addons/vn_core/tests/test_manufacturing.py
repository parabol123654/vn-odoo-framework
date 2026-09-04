# -*- coding: utf-8 -*-
"""Manufacturing Cost Engine tests. No Odoo, no database."""

import unittest
from datetime import date

from ..core.exceptions import ValidationException
from ..domain.manufacturing.engine import ManufacturingCostEngine
from ..domain.manufacturing.repository import IManufacturingRepository
from ..dto.common import CurrencyDTO
from ..dto.filters import ManufacturingFilter
from ..dto.inventory import ProductDTO
from ..dto.manufacturing import ProductionDTO

VND = CurrencyDTO(id=1, name='VND', rounding=1.0, decimal_places=0)

BAN_AN = ProductDTO(1, 'TP001', 'Bộ bàn ăn gỗ sồi', 'Bộ', 'Thành phẩm')
TU_AO = ProductDTO(2, 'TP002', 'Tủ quần áo 4 cánh', 'Cái', 'Thành phẩm')


def _mo(mo_id, product, state='done', finished=date(2026, 3, 15),
        started=date(2026, 3, 1)):
    return ProductionDTO(
        id=mo_id, name='WH/MO/%05d' % mo_id, product=product, state=state,
        date_finished=finished if state == 'done' else None,
        date_started=started)


class FakeManufacturingRepository(IManufacturingRepository):

    def __init__(self, done=(), open_orders=(), materials=None, outputs=None,
                 consumptions=(), currency=VND):
        self.done = tuple(done)
        self.open_orders = tuple(open_orders)
        self.materials = dict(materials or {})
        self.outputs = dict(outputs or {})
        #: Dated issues, ``(production_id, date, value)``. When given they are
        #: the source for ``get_material_costs``, so the date bounds the cost
        #: card passes actually select something; ``materials`` remains the
        #: undated shortcut the older tests use.
        self.consumptions = tuple(consumptions)
        self.currency = currency

    def get_currency(self, company_ids):
        return self.currency

    def get_productions(self, manufacturing_filter, done=True):
        return self.done if done else self.open_orders

    def get_productions_open_at(self, manufacturing_filter, at_date):
        productions = self.done + self.open_orders
        return tuple(
            p for p in productions
            if p.date_started and p.date_started <= at_date
            and (not p.is_done
                 or (p.date_finished and p.date_finished > at_date)))

    def get_material_costs(self, production_ids, date_from=None, date_to=None):
        if not self.consumptions:
            return {k: v for k, v in self.materials.items()
                    if k in production_ids}
        totals = {}
        for production_id, when, value in self.consumptions:
            if production_id not in production_ids:
                continue
            if date_from and when < date_from:
                continue
            if date_to and when > date_to:
                continue
            totals[production_id] = totals.get(production_id, 0.0) + value
        return totals

    def get_outputs(self, production_ids):
        return {k: v for k, v in self.outputs.items() if k in production_ids}


class ManufacturingCase(unittest.TestCase):

    done = ()
    open_orders = ()
    materials = None
    outputs = None

    def setUp(self):
        self.repo = FakeManufacturingRepository(
            self.done, self.open_orders, self.materials, self.outputs)
        self.engine = ManufacturingCostEngine(self.repo)

    def _filter(self, **kw):
        kw.setdefault('date_from', date(2026, 1, 1))
        return ManufacturingFilter(date_to=date(2026, 12, 31),
                                   company_ids=(1,), **kw)

    def _order(self, report, mo_id):
        return next(o for o in report.orders if o.production.id == mo_id)

    def _product(self, report, product_id):
        return next(p for p in report.products if p.product.id == product_id)


class TestOrderCosting(ManufacturingCase):

    done = (_mo(1, BAN_AN), _mo(2, BAN_AN, finished=date(2026, 4, 2)),
            _mo(3, TU_AO, finished=date(2026, 5, 10)))
    materials = {1: 30000000.0, 2: 45000000.0, 3: 18000000.0}
    outputs = {1: (10.0, 30000000.0), 2: (15.0, 45000000.0),
               3: (6.0, 18000000.0)}

    def test_material_cost_per_order(self):
        report = self.engine.compute(self._filter())
        self.assertEqual(self._order(report, 1).material_cost, 30000000.0)

    def test_unit_cost_uses_what_the_ledger_capitalised(self):
        report = self.engine.compute(self._filter())
        self.assertEqual(self._order(report, 1).unit_cost, 3000000.0)

    def test_no_variance_under_moving_average(self):
        """Odoo values the output at exactly the sum of the inputs."""
        report = self.engine.compute(self._filter())
        self.assertEqual(self._order(report, 1).variance, 0.0)

    def test_orders_sorted_by_completion_date(self):
        report = self.engine.compute(self._filter())
        self.assertEqual([o.production.id for o in report.orders], [1, 2, 3])

    def test_totals(self):
        report = self.engine.compute(self._filter())
        self.assertEqual(report.material_cost, 93000000.0)
        self.assertEqual(report.output_value, 93000000.0)


class TestStandardCostingVariance(ManufacturingCase):
    """Under standard costing the output is valued at standard, not at cost."""

    done = (_mo(1, BAN_AN),)
    materials = {1: 30000000.0}
    outputs = {1: (10.0, 32000000.0)}

    def test_variance_is_reported(self):
        report = self.engine.compute(self._filter())
        self.assertEqual(self._order(report, 1).variance, 2000000.0)

    def test_unit_cost_follows_the_ledger_not_the_inputs(self):
        report = self.engine.compute(self._filter())
        self.assertEqual(self._order(report, 1).unit_cost, 3200000.0)


class TestProductSummary(ManufacturingCase):

    done = (_mo(1, BAN_AN), _mo(2, BAN_AN, finished=date(2026, 4, 2)),
            _mo(3, TU_AO, finished=date(2026, 5, 10)))
    materials = {1: 30000000.0, 2: 45000000.0, 3: 18000000.0}
    outputs = {1: (10.0, 30000000.0), 2: (15.0, 45000000.0),
               3: (6.0, 18000000.0)}

    def test_orders_of_one_product_are_pooled(self):
        report = self.engine.compute(self._filter())
        summary = self._product(report, BAN_AN.id)
        self.assertEqual(summary.order_count, 2)
        self.assertEqual(summary.output_quantity, 25.0)
        self.assertEqual(summary.output_value, 75000000.0)

    def test_pooled_unit_cost_is_weighted_not_averaged(self):
        """25 units for 75,000,000 is 3,000,000 — not the mean of two orders."""
        report = self.engine.compute(self._filter())
        self.assertEqual(self._product(report, BAN_AN.id).unit_cost, 3000000.0)

    def test_products_sorted_by_code(self):
        report = self.engine.compute(self._filter())
        self.assertEqual([p.product.code for p in report.products],
                         ['TP001', 'TP002'])


class TestWorkInProgress(ManufacturingCase):
    """Odoo 14 CE has no WIP account, so this figure exists nowhere in the ledger."""

    done = (_mo(1, BAN_AN),)
    open_orders = (_mo(9, TU_AO, state='progress'),
                   _mo(10, BAN_AN, state='confirmed'))
    materials = {1: 30000000.0, 9: 8000000.0, 10: 5000000.0}
    outputs = {1: (10.0, 30000000.0)}

    def test_materials_of_open_orders_are_reported_apart(self):
        report = self.engine.compute(self._filter())
        self.assertEqual(report.work_in_progress, 13000000.0)
        self.assertEqual(report.open_order_count, 2)

    def test_open_orders_are_not_costed_as_finished(self):
        report = self.engine.compute(self._filter())
        self.assertEqual([o.production.id for o in report.orders], [1])
        self.assertEqual(report.material_cost, 30000000.0)

    def test_work_in_progress_can_be_switched_off(self):
        report = self.engine.compute(self._filter(include_open=False))
        self.assertEqual(report.work_in_progress, 0.0)
        self.assertEqual(report.open_order_count, 0)


class TestEdgeCases(ManufacturingCase):

    done = (_mo(1, BAN_AN),)
    materials = {1: 30000000.0}
    outputs = {1: (0.0, 0.0)}

    def test_order_producing_nothing_does_not_divide_by_zero(self):
        report = self.engine.compute(self._filter())
        self.assertEqual(self._order(report, 1).unit_cost, 0.0)

    def test_scrapped_order_shows_its_material_as_variance(self):
        report = self.engine.compute(self._filter())
        self.assertEqual(self._order(report, 1).variance, -30000000.0)


class TestCostCard(ManufacturingCase):
    """Thẻ tính giá thành (S37-DN): mỗi con số đo trực tiếp, không suy nhau.

    March 2026. Order 1 straddles the period start: issued 10,000,000 in
    February, 20,000,000 in March, finished 15 March. Order 2 starts inside the
    period and is still open when it ends. Order 3 belongs to another product
    and is valued at standard, one million above its inputs.
    """

    done = (_mo(1, BAN_AN, finished=date(2026, 3, 15),
                started=date(2026, 2, 10)),
            _mo(3, TU_AO, finished=date(2026, 3, 20),
                started=date(2026, 3, 2)))
    open_orders = (_mo(2, BAN_AN, state='progress', started=date(2026, 3, 20)),)
    outputs = {1: (10.0, 30000000.0), 3: (6.0, 19000000.0)}
    consumptions = (
        (1, date(2026, 2, 15), 10000000.0),
        (1, date(2026, 3, 5), 20000000.0),
        (2, date(2026, 3, 25), 8000000.0),
        (3, date(2026, 3, 5), 18000000.0),
    )

    def setUp(self):
        self.repo = FakeManufacturingRepository(
            self.done, self.open_orders, consumptions=self.consumptions,
            outputs=self.outputs)
        self.engine = ManufacturingCostEngine(self.repo)

    def _filter(self, **kw):
        kw.setdefault('date_from', date(2026, 3, 1))
        kw.setdefault('date_to', date(2026, 3, 31))
        return ManufacturingFilter(company_ids=(1,), **kw)

    def _row(self, report, product_id):
        return next(r for r in report.rows if r.product.id == product_id)

    def test_opening_wip_is_february_consumption_of_the_straddling_order(self):
        report = self.engine.compute_cost_card(self._filter())
        self.assertEqual(self._row(report, BAN_AN.id).opening_wip, 10000000.0)

    def test_period_cost_pools_finished_and_open_orders(self):
        report = self.engine.compute_cost_card(self._filter())
        self.assertEqual(self._row(report, BAN_AN.id).period_cost, 28000000.0)

    def test_closing_wip_is_what_the_open_order_consumed(self):
        report = self.engine.compute_cost_card(self._filter())
        self.assertEqual(self._row(report, BAN_AN.id).closing_wip, 8000000.0)

    def test_the_card_balances_under_moving_average(self):
        """Opening + costs − finished − closing = 0 when output = inputs."""
        report = self.engine.compute_cost_card(self._filter())
        self.assertEqual(self._row(report, BAN_AN.id).imbalance, 0.0)

    def test_standard_costing_shows_its_variance_as_imbalance(self):
        """Order 3 capitalised 19,000,000 from 18,000,000 of inputs."""
        report = self.engine.compute_cost_card(self._filter())
        self.assertEqual(self._row(report, TU_AO.id).imbalance, -1000000.0)

    def test_unit_cost_follows_the_capitalised_value(self):
        report = self.engine.compute_cost_card(self._filter())
        self.assertEqual(self._row(report, BAN_AN.id).unit_cost, 3000000.0)

    def test_totals_cross_foot(self):
        report = self.engine.compute_cost_card(self._filter())
        self.assertEqual(report.total_opening_wip, 10000000.0)
        self.assertEqual(report.total_period_cost, 46000000.0)
        self.assertEqual(report.total_finished_value, 49000000.0)
        self.assertEqual(report.total_closing_wip, 8000000.0)
        self.assertEqual(report.imbalance, -1000000.0)

    def test_rows_sorted_by_product_code(self):
        report = self.engine.compute_cost_card(self._filter())
        self.assertEqual([r.product.code for r in report.rows],
                         ['TP001', 'TP002'])

    def test_no_date_from_means_no_opening_wip(self):
        """An inception-to-date card has nothing before its first day."""
        report = self.engine.compute_cost_card(self._filter(date_from=None))
        self.assertEqual(self._row(report, BAN_AN.id).opening_wip, 0.0)
        # February consumption then belongs to the period itself.
        self.assertEqual(self._row(report, BAN_AN.id).period_cost, 38000000.0)


class TestEmptyAndValidation(ManufacturingCase):

    def test_no_production_in_the_period(self):
        report = self.engine.compute(self._filter())
        self.assertEqual(report.orders, ())
        self.assertEqual(report.products, ())
        self.assertEqual(report.material_cost, 0.0)

    def test_no_company(self):
        with self.assertRaises(ValidationException):
            self.engine.compute(
                ManufacturingFilter(date_to=date(2026, 12, 31),
                                    company_ids=()))

    def test_reversed_dates(self):
        with self.assertRaises(ValidationException):
            self.engine.compute(self._filter(date_from=date(2027, 1, 1)))


if __name__ == '__main__':
    unittest.main()
