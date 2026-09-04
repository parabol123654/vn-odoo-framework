# -*- coding: utf-8 -*-
"""Manufacturing Cost Engine — Báo cáo chi phí sản xuất (Engine 5).

Costs each manufacturing order from its valuation layers, rolls the result up
per product, and reports separately what is still tied up in orders that have
not finished.

**What this engine does not do, and why.** It reports no direct labour and no
production overhead. Odoo 14 Community journalises neither: a workcenter's
``costs_hour`` yields a statistical figure that never reaches account 622 or
627, and the Community edition has no work-in-progress account. A cost sheet
mixing a journalised material cost with a statistical labour cost has one column
that reconciles to the accounts and one that does not, and nothing on the page
tells the reader which. Producing that quietly would be worse than producing
less. Part 17 §6 records what it would take to add them properly.

Pure Python: no Odoo, no SQL.
"""

from datetime import timedelta

from ...core.exceptions import ValidationException
from ...core.utils.number import round_amount
from ...dto.manufacturing import (
    CostCardDTO, CostCardRowDTO, ManufacturingCostDTO, ProductCostSummaryDTO,
    ProductionCostDTO,
)

#: Quantities are not money and keep their own precision.
QUANTITY_ROUNDING = 0.001


class ManufacturingCostEngine:

    def __init__(self, repository):
        self._repo = repository

    # ==================================================================
    # Public API
    # ==================================================================
    def compute(self, manufacturing_filter):
        self._validate(manufacturing_filter)
        currency = self._repo.get_currency(manufacturing_filter.company_ids)
        rounding = currency.rounding

        finished = self._repo.get_productions(manufacturing_filter, done=True)
        orders = self._cost_orders(finished, rounding)

        work_in_progress, open_count = 0.0, 0
        if manufacturing_filter.include_open:
            work_in_progress, open_count = self._work_in_progress(
                manufacturing_filter, rounding)

        return ManufacturingCostDTO(
            orders=orders,
            products=self._summarise(orders, rounding),
            material_cost=round_amount(
                sum(o.material_cost for o in orders), rounding),
            output_value=round_amount(
                sum(o.output_value for o in orders), rounding),
            work_in_progress=work_in_progress,
            open_order_count=open_count,
            currency=currency,
            date_from=manufacturing_filter.date_from,
            date_to=manufacturing_filter.date_to,
        )

    def compute_cost_card(self, manufacturing_filter):
        """Thẻ tính giá thành sản phẩm, dịch vụ (S37-DN).

        Per product: chi phí dở dang đầu kỳ, phát sinh trong kỳ, giá thành
        nhập kho trong kỳ, dở dang cuối kỳ. Each figure is measured directly
        from the valuation layers rather than derived from the other three, so
        a card that does not balance is *reporting* something — a standard-cost
        variance, or consumption recorded outside the period — instead of
        hiding it.

        Direct materials only, for the reason given at the top of this module.
        """
        self._validate(manufacturing_filter)
        currency = self._repo.get_currency(manufacturing_filter.company_ids)
        rounding = currency.rounding

        finished = self._repo.get_productions(manufacturing_filter, done=True)
        open_at_end = self._repo.get_productions_open_at(
            manufacturing_filter, manufacturing_filter.date_to)

        open_at_start, opening_costs = (), {}
        if manufacturing_filter.date_from:
            # WIP as the period opened: consumption strictly before date_from
            # by the orders that were open when it began.
            day_before = manufacturing_filter.date_from - timedelta(days=1)
            open_at_start = self._repo.get_productions_open_at(
                manufacturing_filter, day_before)
            opening_costs = self._repo.get_material_costs(
                tuple(p.id for p in open_at_start), date_to=day_before)

        everything = {p.id: p for p in finished}
        for production in open_at_end + open_at_start:
            everything.setdefault(production.id, production)

        period_costs = self._repo.get_material_costs(
            tuple(everything),
            date_from=manufacturing_filter.date_from,
            date_to=manufacturing_filter.date_to) if everything else {}
        closing_costs = self._repo.get_material_costs(
            tuple(p.id for p in open_at_end),
            date_to=manufacturing_filter.date_to) if open_at_end else {}
        outputs = self._repo.get_outputs(tuple(p.id for p in finished))

        buckets = {}
        for production in everything.values():
            product = production.product
            bucket = buckets.setdefault(product.id, {
                'product': product, 'opening': 0.0, 'period': 0.0,
                'value': 0.0, 'quantity': 0.0, 'closing': 0.0,
                'finished': 0, 'open': 0})
            bucket['period'] += period_costs.get(production.id, 0.0)
        for production in open_at_start:
            buckets[production.product.id]['opening'] += opening_costs.get(
                production.id, 0.0)
        for production in open_at_end:
            bucket = buckets[production.product.id]
            bucket['closing'] += closing_costs.get(production.id, 0.0)
            bucket['open'] += 1
        for production in finished:
            quantity, value = outputs.get(production.id, (0.0, 0.0))
            bucket = buckets[production.product.id]
            bucket['quantity'] += quantity
            bucket['value'] += value
            bucket['finished'] += 1

        rows = [
            CostCardRowDTO(
                product=bucket['product'],
                opening_wip=round_amount(bucket['opening'], rounding),
                period_cost=round_amount(bucket['period'], rounding),
                finished_value=round_amount(bucket['value'], rounding),
                finished_quantity=round_amount(bucket['quantity'],
                                               QUANTITY_ROUNDING),
                closing_wip=round_amount(bucket['closing'], rounding),
                finished_order_count=bucket['finished'],
                open_order_count=bucket['open'],
            )
            for bucket in buckets.values()
        ]
        rows = [row for row in rows if any((
            row.opening_wip, row.period_cost, row.finished_value,
            row.closing_wip))]
        rows.sort(key=lambda r: (r.product.code or '', r.product.name))

        return CostCardDTO(
            rows=tuple(rows),
            total_opening_wip=round_amount(
                sum(r.opening_wip for r in rows), rounding),
            total_period_cost=round_amount(
                sum(r.period_cost for r in rows), rounding),
            total_finished_value=round_amount(
                sum(r.finished_value for r in rows), rounding),
            total_closing_wip=round_amount(
                sum(r.closing_wip for r in rows), rounding),
            currency=currency,
            date_from=manufacturing_filter.date_from,
            date_to=manufacturing_filter.date_to,
        )

    # ==================================================================
    # Internals
    # ==================================================================
    @staticmethod
    def _validate(manufacturing_filter):
        if not manufacturing_filter.company_ids:
            raise ValidationException('No company supplied in the filter.')
        if (manufacturing_filter.date_from
                and manufacturing_filter.date_from > manufacturing_filter.date_to):
            raise ValidationException('date_from must precede date_to.')

    def _cost_orders(self, productions, rounding):
        ids = tuple(p.id for p in productions)
        if not ids:
            return ()
        materials = self._repo.get_material_costs(ids)
        outputs = self._repo.get_outputs(ids)

        orders = []
        for production in productions:
            quantity, value = outputs.get(production.id, (0.0, 0.0))
            orders.append(ProductionCostDTO(
                production=production,
                material_cost=round_amount(
                    materials.get(production.id, 0.0), rounding),
                output_quantity=round_amount(quantity, QUANTITY_ROUNDING),
                output_value=round_amount(value, rounding),
            ))
        orders.sort(key=lambda o: (o.production.date_finished or o.production.name,
                                   o.production.name))
        return tuple(orders)

    def _summarise(self, orders, rounding):
        """Roll orders up per product, which is how VAS presents a cost sheet."""
        buckets = {}
        for order in orders:
            product = order.production.product
            bucket = buckets.setdefault(product.id, {
                'product': product, 'count': 0,
                'material': 0.0, 'quantity': 0.0, 'value': 0.0})
            bucket['count'] += 1
            bucket['material'] += order.material_cost
            bucket['quantity'] += order.output_quantity
            bucket['value'] += order.output_value

        summaries = [
            ProductCostSummaryDTO(
                product=bucket['product'],
                order_count=bucket['count'],
                material_cost=round_amount(bucket['material'], rounding),
                output_quantity=round_amount(bucket['quantity'],
                                             QUANTITY_ROUNDING),
                output_value=round_amount(bucket['value'], rounding),
            )
            for bucket in buckets.values()
        ]
        summaries.sort(key=lambda s: (s.product.code or '', s.product.name))
        return tuple(summaries)

    def _work_in_progress(self, manufacturing_filter, rounding):
        """Materials issued to orders that had not finished by the date.

        Odoo 14 Community has no work-in-progress account, so this figure exists
        nowhere in the ledger. It is derived from the components already
        consumed by orders still open, which is the same thing an accountant
        computes by hand for the 154 balance.
        """
        open_orders = self._repo.get_productions(manufacturing_filter,
                                                 done=False)
        if not open_orders:
            return 0.0, 0
        materials = self._repo.get_material_costs(
            tuple(p.id for p in open_orders))
        return (round_amount(sum(materials.values()), rounding),
                len(open_orders))
