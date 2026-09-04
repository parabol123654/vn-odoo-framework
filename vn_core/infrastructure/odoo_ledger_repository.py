# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Odoo implementation of ``ILedgerRepository`` (Part 6 §7).

The only module in the ledger stack that touches the ORM or SQL. It contains no
business logic: no fiscal-year rule, no side detection, no sign handling. It
receives an explicit date window and returns DTOs.

Two Odoo-specific requirements are honoured throughout:

* ``flush()`` before raw SQL, or pending ORM writes in the current transaction
  are invisible to the cursor.
* ``_where_calc`` + ``_apply_ir_rules`` to build the WHERE clause, so record
  rules — multi-company above all — are enforced rather than bypassed. Part 13
  §10 permits SQL only under this condition.
"""

from odoo import fields as odoo_fields

from ..domain.ledger.repository import ILedgerRepository
from ..dto.common import (
    AnalyticAccountDTO, AccountDTO, CompanyDTO, CurrencyDTO, JournalDTO,
    PartnerDTO,
)
from ..dto.inventory import ProductDTO
from ..dto.ledger import BalanceDTO, MoveAccountSumDTO, MoveLineDTO
from ..core.exceptions import RepositoryException
from .base_repository import BaseRepository

AML = 'account.move.line'
ALIAS = '"account_move_line"'

# Whitelist of groupable columns. Guards the interpolated GROUP BY.
GROUPABLE = ('account_id', 'partner_id', 'journal_id', 'analytic_account_id')


class OdooLedgerRepository(ILedgerRepository, BaseRepository):

    # ==================================================================
    # Reference data
    # ==================================================================
    def get_companies(self, company_ids):
        companies = self.env['res.company'].browse(list(company_ids)).exists()
        return tuple(
            CompanyDTO(
                id=company.id,
                name=company.name,
                currency=CurrencyDTO(
                    id=company.currency_id.id,
                    name=company.currency_id.name,
                    rounding=company.currency_id.rounding,
                    decimal_places=company.currency_id.decimal_places,
                ),
                fiscalyear_last_day=company.fiscalyear_last_day,
                fiscalyear_last_month=int(company.fiscalyear_last_month),
            )
            for company in companies
        )

    def get_accounts(self, ledger_filter):
        domain = [('company_id', 'in', list(ledger_filter.company_ids))]
        if ledger_filter.account_ids:
            domain.append(('id', 'in', list(ledger_filter.account_ids)))
        if ledger_filter.account_type_ids:
            domain.append(
                ('user_type_id', 'in', list(ledger_filter.account_type_ids)))
        accounts = self.env['account.account'].search(domain)
        return tuple(
            AccountDTO(
                id=account.id,
                code=account.code or '',
                name=account.name or '',
                include_initial_balance=bool(
                    account.user_type_id.include_initial_balance),
                internal_group=account.internal_group or '',
            )
            for account in accounts
        )

    def get_partners(self, partner_ids):
        partners = self.env['res.partner'].browse(list(partner_ids)).exists()
        return tuple(
            PartnerDTO(id=p.id, name=p.name or '', ref=p.ref or '')
            for p in partners
        )

    def get_products(self, product_ids):
        products = self.env['product.product'].browse(list(product_ids)).exists()
        return tuple(
            ProductDTO(
                id=p.id,
                code=p.default_code or '',
                name=p.name or '',
                uom_name=p.uom_id.name or '',
                category_name=p.categ_id.complete_name or '',
            )
            for p in products
        )

    def get_journals(self, journal_ids):
        journals = self.env['account.journal'].browse(list(journal_ids)).exists()
        return tuple(
            JournalDTO(id=j.id, code=j.code or '', name=j.name or '')
            for j in journals
        )

    def get_analytic_accounts(self, analytic_ids):
        records = self.env['account.analytic.account'].browse(
            list(analytic_ids)).exists()
        return tuple(
            AnalyticAccountDTO(id=a.id, code=a.code or '', name=a.name or '')
            for a in records
        )

    # ==================================================================
    # Aggregates
    # ==================================================================
    def aggregate_balances(self, ledger_filter, group_by, date_from, date_to,
                           account_ids=None, company_ids=None):
        for field in group_by:
            if field not in GROUPABLE:
                raise RepositoryException(
                    'Column %r is not groupable.' % (field,))

        domain = self._build_domain(
            ledger_filter, date_from, date_to,
            account_ids=account_ids, company_ids=company_ids)
        from_clause, where_clause, params = self._query_parts(domain)

        select_group = ''.join(
            '%s.%s AS %s, ' % (ALIAS, field, field) for field in group_by)
        group_clause = ''
        if group_by:
            group_clause = 'GROUP BY ' + ', '.join(
                '%s.%s' % (ALIAS, field) for field in group_by)

        sql = """
            SELECT {select_group}
                   COALESCE(SUM({alias}.debit), 0.0)   AS debit,
                   COALESCE(SUM({alias}.credit), 0.0)  AS credit,
                   COALESCE(SUM({alias}.balance), 0.0) AS balance
              FROM {from_clause}
             WHERE {where_clause}
             {group_clause}
        """.format(select_group=select_group, alias=ALIAS,
                   from_clause=from_clause, where_clause=where_clause,
                   group_clause=group_clause)

        self.cr.execute(sql, params)
        result = {}
        for row in self.cr.dictfetchall():
            key = tuple(row[field] for field in group_by)
            result[key] = BalanceDTO(row['debit'], row['credit'], row['balance'])
        return result

    # ==================================================================
    # Detail
    # ==================================================================
    def get_move_lines(self, ledger_filter):
        domain = self._build_domain(
            ledger_filter, ledger_filter.date_from, ledger_filter.date_to)
        from_clause, where_clause, params = self._query_parts(domain)

        sql = """
            SELECT {alias}.id,
                   {alias}.date,
                   {alias}.name          AS label,
                   {alias}.ref,
                   {alias}.debit,
                   {alias}.credit,
                   {alias}.balance,
                   {alias}.amount_currency,
                   {alias}.currency_id,
                   {alias}.company_id,
                   {alias}.account_id,
                   {alias}.partner_id,
                   {alias}.journal_id,
                   {alias}.move_id,
                   {alias}.analytic_account_id,
                   {alias}.date_maturity,
                   {alias}.amount_residual,
                   {alias}.full_reconcile_id,
                   {alias}.parent_state,
                   {alias}.product_id,
                   {alias}.quantity,
                   am.name               AS move_name,
                   {voucher}             AS voucher_number
              FROM {from_clause}
              JOIN account_move am ON am.id = {alias}.move_id
             WHERE {where_clause}
          ORDER BY {alias}.date, {alias}.move_id, {alias}.id
        """.format(alias=ALIAS, from_clause=from_clause,
                   where_clause=where_clause,
                   voucher=self._voucher_number_expression())

        self.cr.execute(sql, params)
        return tuple(
            MoveLineDTO(
                id=row['id'],
                date=row['date'],
                account_id=row['account_id'],
                journal_id=row['journal_id'],
                move_id=row['move_id'],
                move_name=row['move_name'] or '/',
                debit=row['debit'],
                credit=row['credit'],
                balance=row['balance'],
                label=row['label'] or '',
                ref=row['ref'] or '',
                partner_id=row['partner_id'],
                analytic_account_id=row['analytic_account_id'],
                currency_id=row['currency_id'],
                amount_currency=row['amount_currency'] or 0.0,
                date_maturity=row['date_maturity'],
                amount_residual=row['amount_residual'] or 0.0,
                full_reconcile_id=row['full_reconcile_id'],
                company_id=row['company_id'],
                state=row['parent_state'] or 'posted',
                voucher_number=row.get('voucher_number') or '',
                product_id=row['product_id'],
                quantity=row['quantity'] or 0.0,
            )
            for row in self.cr.dictfetchall()
        )

    def get_move_account_sums(self, move_ids):
        if not move_ids:
            return ()
        self.env[AML].flush()
        self.cr.execute("""
            SELECT move_id, account_id,
                   SUM(debit)  AS debit,
                   SUM(credit) AS credit
              FROM account_move_line
             WHERE move_id IN %s
          GROUP BY move_id, account_id
        """, (tuple(move_ids),))
        return tuple(
            MoveAccountSumDTO(row['move_id'], row['account_id'],
                              row['debit'], row['credit'])
            for row in self.cr.dictfetchall()
        )

    # ==================================================================
    # Reconciliation
    # ==================================================================
    def get_reconciled_after(self, line_ids, date_to):
        if not line_ids:
            return {}
        self.env['account.partial.reconcile'].flush()
        self.cr.execute("""
            SELECT line_id, SUM(amount) AS amount FROM (
                SELECT pr.debit_move_id AS line_id, pr.amount AS amount
                  FROM account_partial_reconcile pr
                 WHERE pr.debit_move_id IN %(ids)s
                   AND pr.max_date > %(date_to)s
                UNION ALL
                SELECT pr.credit_move_id AS line_id, -pr.amount AS amount
                  FROM account_partial_reconcile pr
                 WHERE pr.credit_move_id IN %(ids)s
                   AND pr.max_date > %(date_to)s
            ) matched
          GROUP BY line_id
        """, {'ids': tuple(line_ids), 'date_to': date_to})
        return {row['line_id']: row['amount']
                for row in self.cr.dictfetchall()}

    # ==================================================================
    # Internals
    # ==================================================================
    def _voucher_number_expression(self):
        """SQL for the cash voucher number, when the column exists.

        ``vn_voucher_number`` is added by the localisation module, and vn_core
        does not depend on it — the framework must install and run on its own.
        So the column is detected in the registry rather than assumed, and the
        query falls back to NULL when the localisation is absent. Writing the
        column name unconditionally would make the framework fail to install
        without a module it is not supposed to require.
        """
        if 'vn_voucher_number' in self.env['account.move']._fields:
            return 'am.vn_voucher_number'
        return 'NULL::varchar'

    def _build_domain(self, ledger_filter, date_from, date_to,
                      account_ids=None, company_ids=None):
        companies = company_ids if company_ids else ledger_filter.company_ids
        domain = [('company_id', 'in', list(companies))]

        # parent_state is a stored related field on AML in 14, so this is an
        # indexed filter rather than a join. Cancelled moves are always out.
        if ledger_filter.posted_only:
            domain.append(('parent_state', '=', 'posted'))
        else:
            domain.append(('parent_state', 'in', ('posted', 'draft')))

        if date_from:
            domain.append(('date', '>=', odoo_fields.Date.to_string(date_from)))
        domain.append(('date', '<=', odoo_fields.Date.to_string(date_to)))

        selected_accounts = (account_ids if account_ids is not None
                             else ledger_filter.account_ids)
        if selected_accounts:
            domain.append(('account_id', 'in', list(selected_accounts)))

        for field, values in (
            ('partner_id', ledger_filter.partner_ids),
            ('journal_id', ledger_filter.journal_ids),
            ('analytic_account_id', ledger_filter.analytic_account_ids),
            ('analytic_tag_ids', ledger_filter.analytic_tag_ids),
            ('product_id', ledger_filter.product_ids),
        ):
            if values:
                domain.append((field, 'in', list(values)))
        return domain

    def _query_parts(self, domain):
        """``(from_clause, where_clause, params)`` with record rules applied."""
        model = self.env[AML]
        model.flush()
        query = model._where_calc(domain)
        model._apply_ir_rules(query, 'read')
        return query.get_sql()
