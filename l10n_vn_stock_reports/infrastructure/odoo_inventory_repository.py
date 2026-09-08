# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""Odoo implementation of ``IInventoryRepository``.

Reads ``stock.valuation.layer``. That choice is the whole point: the layer is
what Odoo posted to accounts 152/155/156, so a stock report built on it agrees
with the general ledger by construction. Taking quantity from ``stock.move`` and
multiplying by a current cost would produce a report that looks right and
disagrees with the ledger the moment a cost changes.

**Which date a layer belongs to.** A valuation layer has no accounting date of
its own in Odoo 14; it carries ``create_date``, which is when the record was
written rather than when the movement happened. The effective date lives on the
originating ``stock.move``, so that is used whenever there is one, falling back
to ``create_date`` for layers with no move — inventory revaluations, mainly.
Backdating a stock move after the fact will therefore report under the move's
date, which is what an accountant expects.
"""

from odoo import fields as odoo_fields

from odoo.addons.vn_core.domain.inventory.repository import IInventoryRepository
from odoo.addons.vn_core.dto.common import CurrencyDTO
from odoo.addons.vn_core.dto.inventory import (
    InventoryBalanceDTO, InventoryMoveDTO, ProductDTO,
)
from odoo.addons.vn_core.infrastructure.base_repository import BaseRepository

SVL = 'stock.valuation.layer'
ALIAS = '"stock_valuation_layer"'
#: The effective date of a layer, with the fallback described above.
DATE_EXPR = 'COALESCE(sm.date, %s.create_date)' % ALIAS


class OdooInventoryRepository(IInventoryRepository, BaseRepository):

    # ------------------------------------------------------------------
    def get_currency(self, company_ids):
        company = self.env['res.company'].browse(list(company_ids))[:1]
        currency = company.currency_id or self.env.company.currency_id
        return CurrencyDTO(
            id=currency.id, name=currency.name,
            rounding=currency.rounding, decimal_places=currency.decimal_places)

    def get_products(self, inventory_filter):
        domain = [('is_storable', '=', True)]
        if inventory_filter.product_ids:
            domain.append(('id', 'in', list(inventory_filter.product_ids)))
        if inventory_filter.category_ids:
            domain.append(
                ('categ_id', 'child_of', list(inventory_filter.category_ids)))
        products = self.env['product.product'].search(domain)
        return tuple(
            ProductDTO(
                id=product.id,
                code=product.default_code or '',
                name=product.name or '',
                uom_name=product.uom_id.name or '',
                category_name=product.categ_id.complete_name or '',
            )
            for product in products
        )

    # ------------------------------------------------------------------
    def get_opening(self, inventory_filter):
        if not inventory_filter.date_from:
            return {}
        return self._aggregate(inventory_filter, upper=inventory_filter.date_from,
                               inclusive=False)

    def _aggregate(self, inventory_filter, upper, inclusive):
        from_clause, where_clause, params = self._query_parts(inventory_filter)
        operator = '<=' if inclusive else '<'
        sql = """
            SELECT {alias}.product_id                AS product_id,
                   SUM({alias}.quantity)             AS quantity,
                   SUM({alias}.value)                AS value
              FROM {from_clause}
              LEFT JOIN stock_move sm ON sm.id = {alias}.stock_move_id
             WHERE {where_clause}
               AND {date_expr} {operator} %s
          GROUP BY {alias}.product_id
        """.format(alias=ALIAS, from_clause=from_clause,
                   where_clause=where_clause, date_expr=DATE_EXPR,
                   operator=operator)
        self.cr.execute(sql, params + [odoo_fields.Date.to_string(upper)])
        return {
            row['product_id']: InventoryBalanceDTO(row['quantity'] or 0.0,
                                                   row['value'] or 0.0)
            for row in self.cr.dictfetchall()
        }

    # ------------------------------------------------------------------
    def get_movements(self, inventory_filter):
        from_clause, where_clause, params = self._query_parts(inventory_filter)
        bounds = []
        if inventory_filter.date_from:
            bounds.append(('%s >= %%s' % DATE_EXPR,
                           odoo_fields.Date.to_string(inventory_filter.date_from)))
        # The layer dates are timestamps, so a bare date here means midnight
        # and silently drops everything that moved during the closing day
        # itself. Same convention as the manufacturing repository.
        bounds.append(('%s <= %%s' % DATE_EXPR,
                       '%s 23:59:59' % odoo_fields.Date.to_string(
                           inventory_filter.date_to)))

        # "TK đối ứng" for S10-DN: the accounts on the other side of the
        # journal entry the layer posted. The stock account sits on the same
        # side as the layer's sign — debit on a receipt, credit on an issue —
        # so the counterpart is whatever the entry carries on the opposite
        # side. A layer with no entry (periodic inventory) prints nothing.
        counterpart_expr = """
            (SELECT string_agg(
                        DISTINCT aa.code_store->>(aml.company_id::text),
                        ', ')
               FROM account_move_line aml
               JOIN account_account aa ON aa.id = aml.account_id
              WHERE aml.move_id = {alias}.account_move_id
                AND CASE WHEN {alias}.value >= 0
                         THEN aml.credit ELSE aml.debit END > 0)
        """.format(alias=ALIAS)

        sql = """
            SELECT {alias}.id                        AS id,
                   {date_expr}                       AS move_date,
                   {alias}.product_id                AS product_id,
                   {alias}.quantity                  AS quantity,
                   {alias}.value                     AS value,
                   {alias}.unit_cost                 AS unit_cost,
                   {alias}.description               AS description,
                   {alias}.stock_move_id             AS stock_move_id,
                   sm.reference                      AS reference,
                   rp.name                           AS partner_name,
                   {counterpart_expr}                AS counterpart
              FROM {from_clause}
              LEFT JOIN stock_move sm ON sm.id = {alias}.stock_move_id
              LEFT JOIN stock_picking sp ON sp.id = sm.picking_id
              LEFT JOIN res_partner rp ON rp.id = sp.partner_id
             WHERE {where_clause}
               AND {bounds}
          ORDER BY {date_expr}, {alias}.id
        """.format(alias=ALIAS, from_clause=from_clause,
                   where_clause=where_clause, date_expr=DATE_EXPR,
                   counterpart_expr=counterpart_expr,
                   bounds=' AND '.join(clause for clause, _ in bounds))

        self.cr.execute(sql, params + [value for _, value in bounds])
        return tuple(
            InventoryMoveDTO(
                id=row['id'],
                date=row['move_date'],
                product_id=row['product_id'],
                quantity=row['quantity'] or 0.0,
                value=row['value'] or 0.0,
                unit_cost=row['unit_cost'] or 0.0,
                reference=row['reference'] or '',
                description=row['description'] or '',
                partner_name=row['partner_name'] or '',
                move_id=row['stock_move_id'],
                counterpart=row['counterpart'] or '',
            )
            for row in self.cr.dictfetchall()
        )

    # ------------------------------------------------------------------
    def _build_domain(self, inventory_filter):
        domain = [('company_id', 'in', list(inventory_filter.company_ids))]
        if inventory_filter.product_ids:
            domain.append(('product_id', 'in', list(inventory_filter.product_ids)))
        if inventory_filter.category_ids:
            domain.append(('product_id.categ_id', 'child_of',
                           list(inventory_filter.category_ids)))
        return domain

    def _query_parts(self, inventory_filter):
        """WHERE clause with record rules applied, as for the ledger."""
        model = self.env[SVL]
        model.flush_model()
        self.env['stock.move'].flush_model()
        query = model._where_calc(self._build_domain(inventory_filter))
        model._apply_ir_rules(query, 'read')
        from_sql, where_sql = query.from_clause, query.where_clause
        return (from_sql.code, where_sql.code,
                list(from_sql.params) + list(where_sql.params))
