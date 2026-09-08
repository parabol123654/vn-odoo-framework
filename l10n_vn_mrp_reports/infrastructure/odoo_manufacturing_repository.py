# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""Odoo implementation of ``IManufacturingRepository``.

Cost and quantity both come from ``stock.valuation.layer``, joined to the moves
that a manufacturing order owns:

* components carry ``stock_move.raw_material_production_id``, and their layers
  are negative because the value left stock — so the material cost is the
  negated sum;
* the finished goods carry ``stock_move.production_id``, and their layer is
  the value Odoo capitalised into account 155.

Taking the output quantity from the same layer as the output value, rather than
from ``qty_produced`` on the order, keeps the two consistent: a unit cost
computed from a quantity and a value that came from different places is a unit
cost that can disagree with both.
"""

from odoo import fields as odoo_fields

from odoo.addons.vn_core.domain.manufacturing.repository import (
    IManufacturingRepository,
)
from odoo.addons.vn_core.dto.common import CurrencyDTO
from odoo.addons.vn_core.dto.inventory import ProductDTO
from odoo.addons.vn_core.dto.manufacturing import ProductionDTO
from odoo.addons.vn_core.infrastructure.base_repository import BaseRepository

#: States an order passes through before it has produced anything final.
OPEN_STATES = ('draft', 'confirmed', 'planned', 'progress', 'to_close')


class OdooManufacturingRepository(IManufacturingRepository, BaseRepository):

    def get_currency(self, company_ids):
        company = self.env['res.company'].browse(list(company_ids))[:1]
        currency = company.currency_id or self.env.company.currency_id
        return CurrencyDTO(
            id=currency.id, name=currency.name,
            rounding=currency.rounding, decimal_places=currency.decimal_places)

    # ------------------------------------------------------------------
    def get_productions(self, manufacturing_filter, done=True):
        domain = [('company_id', 'in', list(manufacturing_filter.company_ids))]

        if done:
            domain.append(('state', '=', 'done'))
            # An order is costed when it finishes, so the period selects on the
            # completion date rather than on when it was planned.
            if manufacturing_filter.date_from:
                domain.append(('date_finished', '>=', odoo_fields.Date.to_string(
                    manufacturing_filter.date_from)))
            domain.append(('date_finished', '<=', '%s 23:59:59' % (
                odoo_fields.Date.to_string(manufacturing_filter.date_to))))
        else:
            # Still open *at the reporting date*: started on or before it, and
            # not finished. Orders opened afterwards are not yet anybody's WIP.
            domain += [
                ('state', 'in', list(OPEN_STATES)),
                ('date_start', '<=', '%s 23:59:59' % (
                    odoo_fields.Date.to_string(manufacturing_filter.date_to))),
            ]

        domain += self._scope_domain(manufacturing_filter)
        return self._to_dtos(self.env['mrp.production'].search(domain))

    def get_productions_open_at(self, manufacturing_filter, at_date):
        """WIP as it stood at the end of ``at_date``.

        ``done=False`` above answers "what is open now, as of the report date";
        this answers the historical question the cost card asks — so an order
        that has since finished still counts if it was unfinished on that date.
        """
        end_of_day = '%s 23:59:59' % odoo_fields.Date.to_string(at_date)
        domain = [
            ('company_id', 'in', list(manufacturing_filter.company_ids)),
            ('date_start', '<=', end_of_day),
            '|', ('state', 'in', list(OPEN_STATES)),
            '&', ('state', '=', 'done'), ('date_finished', '>', end_of_day),
        ] + self._scope_domain(manufacturing_filter)
        return self._to_dtos(self.env['mrp.production'].search(domain))

    @staticmethod
    def _scope_domain(manufacturing_filter):
        domain = []
        if manufacturing_filter.production_ids:
            domain.append(('id', 'in', list(manufacturing_filter.production_ids)))
        if manufacturing_filter.product_ids:
            domain.append(
                ('product_id', 'in', list(manufacturing_filter.product_ids)))
        if manufacturing_filter.category_ids:
            domain.append(('product_id.categ_id', 'child_of',
                           list(manufacturing_filter.category_ids)))
        return domain

    @staticmethod
    def _to_dtos(productions):
        return tuple(
            ProductionDTO(
                id=production.id,
                name=production.name or '',
                product=ProductDTO(
                    id=production.product_id.id,
                    code=production.product_id.default_code or '',
                    name=production.product_id.name or '',
                    uom_name=production.product_uom_id.name or '',
                    category_name=production.product_id.categ_id.complete_name or '',
                ),
                state=production.state,
                date_finished=(production.date_finished.date()
                               if production.date_finished else None),
                date_started=(production.date_start.date()
                              if production.date_start else None),
            )
            for production in productions
        )

    # ------------------------------------------------------------------
    def get_material_costs(self, production_ids, date_from=None, date_to=None):
        if not production_ids:
            return {}
        self._flush()
        # The consumption date follows the same rule as the inventory reports:
        # the stock move carries the effective date, and a layer without one
        # (revaluations) falls back to when it was written.
        bounds, params = '', [tuple(production_ids)]
        if date_from:
            bounds += " AND COALESCE(sm.date, svl.create_date) >= %s"
            params.append(odoo_fields.Date.to_string(date_from))
        if date_to:
            bounds += " AND COALESCE(sm.date, svl.create_date) <= %s"
            params.append('%s 23:59:59' % odoo_fields.Date.to_string(date_to))
        self.cr.execute("""
            SELECT sm.raw_material_production_id  AS production_id,
                   COALESCE(SUM(svl.value), 0.0)  AS value
              FROM stock_valuation_layer svl
              JOIN stock_move sm ON sm.id = svl.stock_move_id
             WHERE sm.raw_material_production_id IN %%s%s
          GROUP BY sm.raw_material_production_id
        """ % bounds, params)
        # Components leave stock, so their layers are negative. The cost of the
        # order is what left.
        return {row['production_id']: -(row['value'] or 0.0)
                for row in self.cr.dictfetchall()}

    def get_outputs(self, production_ids):
        if not production_ids:
            return {}
        self._flush()
        self.cr.execute("""
            SELECT sm.production_id                   AS production_id,
                   COALESCE(SUM(svl.quantity), 0.0)   AS quantity,
                   COALESCE(SUM(svl.value), 0.0)      AS value
              FROM stock_valuation_layer svl
              JOIN stock_move sm ON sm.id = svl.stock_move_id
             WHERE sm.production_id IN %s
          GROUP BY sm.production_id
        """, (tuple(production_ids),))
        return {row['production_id']: (row['quantity'] or 0.0,
                                       row['value'] or 0.0)
                for row in self.cr.dictfetchall()}

    def _flush(self):
        self.env['stock.valuation.layer'].flush_model()
        self.env['stock.move'].flush_model()
