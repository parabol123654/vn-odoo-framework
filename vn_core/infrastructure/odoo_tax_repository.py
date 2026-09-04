# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Odoo implementation of ``ITaxRepository``.

Reads the **tax lines** of each move — those with ``tax_line_id`` set — rather
than the base lines. Each tax line already carries ``tax_base_amount``, so one
invoice with twenty product lines yields one row per rate instead of twenty, and
the grouping happens in PostgreSQL rather than in Python.

Odoo may split a tax into several tax lines on one move when the tax posts to
different accounts or analytic accounts, so the query still sums per
``(move, tax)``.

The invoice number is taken from ``ref`` when present, falling back to the move
name. A Vietnamese e-invoice number issued by a provider such as Viettel or VNPT
is normally written to ``ref``; if a client stores it in a custom field,
override ``_invoice_number_column``.
"""

from odoo import fields as odoo_fields

from ..core.enums import TaxDirection
from ..domain.tax.repository import ITaxRepository
from ..dto.common import CurrencyDTO
from ..dto.tax import TaxLineDTO
from .base_repository import BaseRepository

AML = 'account.move.line'
ALIAS = '"account_move_line"'

MOVE_TYPES = {
    TaxDirection.SALE: ('out_invoice', 'out_refund', 'out_receipt'),
    TaxDirection.PURCHASE: ('in_invoice', 'in_refund', 'in_receipt'),
}
TAX_TYPES = {TaxDirection.SALE: 'sale', TaxDirection.PURCHASE: 'purchase'}


class OdooTaxRepository(ITaxRepository, BaseRepository):

    #: Column holding the statutory invoice number.
    _invoice_number_column = 'ref'

    def get_currency(self, company_ids):
        company = self.env['res.company'].browse(list(company_ids))[:1]
        currency = company.currency_id or self.env.company.currency_id
        return CurrencyDTO(
            id=currency.id, name=currency.name,
            rounding=currency.rounding, decimal_places=currency.decimal_places)

    # ------------------------------------------------------------------
    def get_tax_lines(self, ledger_filter, direction):
        domain = self._build_domain(ledger_filter, direction)
        from_clause, where_clause, params = self._query_parts(domain)

        sql = """
            SELECT {alias}.move_id                       AS move_id,
                   {alias}.tax_line_id                   AS tax_id,
                   MIN(am.name)                          AS move_name,
                   MIN(COALESCE(NULLIF(am.{number}, ''), am.name)) AS invoice_number,
                   MIN(COALESCE(am.invoice_date, am.date)) AS invoice_date,
                   MIN(am.move_type)                     AS move_type,
                   MIN(am.partner_id)                    AS partner_id,
                   SUM({alias}.tax_base_amount)          AS base_amount,
                   SUM({alias}.balance)                  AS tax_amount
              FROM {from_clause}
              JOIN account_move am ON am.id = {alias}.move_id
             WHERE {where_clause}
          GROUP BY {alias}.move_id, {alias}.tax_line_id
        """.format(alias=ALIAS, from_clause=from_clause,
                   where_clause=where_clause,
                   number=self._invoice_number_column)

        self.cr.execute(sql, params)
        rows = self.cr.dictfetchall()
        if not rows:
            return ()

        taxes = self._tax_index({row['tax_id'] for row in rows})
        partners = self._partner_index(
            {row['partner_id'] for row in rows if row['partner_id']})

        result = []
        for row in rows:
            tax = taxes.get(row['tax_id'])
            partner = partners.get(row['partner_id'])
            result.append(TaxLineDTO(
                move_id=row['move_id'],
                move_name=row['move_name'] or '/',
                invoice_number=row['invoice_number'] or row['move_name'] or '/',
                invoice_date=row['invoice_date'],
                partner_id=row['partner_id'],
                partner_name=partner['name'] if partner else '',
                partner_vat=partner['vat'] if partner else '',
                tax_id=row['tax_id'],
                tax_name=tax['name'] if tax else '',
                tax_rate=tax['amount'] if tax else 0.0,
                base_amount=row['base_amount'] or 0.0,
                tax_amount=row['tax_amount'] or 0.0,
                move_type=row['move_type'] or 'entry',
            ))
        return tuple(result)

    # ------------------------------------------------------------------
    def _build_domain(self, ledger_filter, direction):
        domain = [
            ('company_id', 'in', list(ledger_filter.company_ids)),
            ('tax_line_id', '!=', False),
            ('move_id.move_type', 'in', list(MOVE_TYPES[direction])),
        ]
        # A percentage tax with amount_type other than 'percent' would make the
        # rate column meaningless, so the scope is deliberately narrow.
        domain.append(('tax_line_id.type_tax_use', '=', TAX_TYPES[direction]))

        if ledger_filter.posted_only:
            domain.append(('parent_state', '=', 'posted'))
        else:
            domain.append(('parent_state', 'in', ('posted', 'draft')))
        if ledger_filter.date_from:
            domain.append(
                ('date', '>=', odoo_fields.Date.to_string(ledger_filter.date_from)))
        domain.append(
            ('date', '<=', odoo_fields.Date.to_string(ledger_filter.date_to)))
        if ledger_filter.partner_ids:
            domain.append(('partner_id', 'in', list(ledger_filter.partner_ids)))
        if ledger_filter.journal_ids:
            domain.append(('journal_id', 'in', list(ledger_filter.journal_ids)))
        return domain

    def _query_parts(self, domain):
        model = self.env[AML]
        model.flush()
        query = model._where_calc(domain)
        model._apply_ir_rules(query, 'read')
        return query.get_sql()

    def _tax_index(self, tax_ids):
        taxes = self.env['account.tax'].browse(
            [i for i in tax_ids if i]).exists()
        return {t.id: {'name': t.name, 'amount': t.amount} for t in taxes}

    def _partner_index(self, partner_ids):
        partners = self.env['res.partner'].browse(list(partner_ids)).exists()
        return {p.id: {'name': p.name or '', 'vat': p.vat or ''}
                for p in partners}
