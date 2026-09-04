# -*- coding: utf-8 -*-
"""In-memory ``ILedgerRepository`` for Domain unit tests.

The existence of this class is the point of the architecture: the Engine talks to
an interface, so the entire accounting calculation can be tested with no
PostgreSQL, no ORM and no Odoo registry. It also serves as a second
implementation of the contract, which keeps the interface honest.
"""

from ..domain.ledger.repository import ILedgerRepository
from ..dto.ledger import BalanceDTO, MoveAccountSumDTO


class FakeLedgerRepository(ILedgerRepository):

    def __init__(self, companies=(), accounts=(), lines=(), partners=(),
                 journals=(), analytic_accounts=(), products=(),
                 reconciled_after=None):
        self.companies = tuple(companies)
        self.accounts = tuple(accounts)
        self.lines = tuple(lines)
        self.partners = tuple(partners)
        self.journals = tuple(journals)
        self.analytic_accounts = tuple(analytic_accounts)
        self.products = tuple(products)
        self.reconciled_after = dict(reconciled_after or {})
        #: Every aggregate query issued, so tests can assert query counts.
        self.aggregate_calls = []

    # -- reference data ------------------------------------------------
    def get_companies(self, company_ids):
        return tuple(c for c in self.companies if c.id in tuple(company_ids))

    def get_accounts(self, ledger_filter):
        accounts = self.accounts
        if ledger_filter.account_ids:
            accounts = tuple(a for a in accounts
                             if a.id in ledger_filter.account_ids)
        return accounts

    def get_partners(self, partner_ids):
        return tuple(p for p in self.partners if p.id in tuple(partner_ids))

    def get_products(self, product_ids):
        return tuple(p for p in self.products if p.id in tuple(product_ids))

    def get_journals(self, journal_ids):
        return tuple(j for j in self.journals if j.id in tuple(journal_ids))

    def get_analytic_accounts(self, analytic_ids):
        return tuple(a for a in self.analytic_accounts
                     if a.id in tuple(analytic_ids))

    # -- aggregates ----------------------------------------------------
    def aggregate_balances(self, ledger_filter, group_by, date_from, date_to,
                           account_ids=None, company_ids=None):
        self.aggregate_calls.append(
            (tuple(group_by), date_from, date_to,
             tuple(account_ids) if account_ids is not None else None))

        result = {}
        for line in self._select(ledger_filter, date_from, date_to,
                                account_ids, company_ids):
            key = tuple(getattr(line, field) for field in group_by)
            current = result.get(key, BalanceDTO())
            result[key] = BalanceDTO(
                current.debit + line.debit,
                current.credit + line.credit,
                current.balance + line.balance,
            )
        return result

    # -- detail --------------------------------------------------------
    def get_move_lines(self, ledger_filter):
        lines = self._select(ledger_filter, ledger_filter.date_from,
                             ledger_filter.date_to, None, None)
        return tuple(sorted(lines, key=lambda l: (l.date, l.move_id, l.id)))

    def get_move_account_sums(self, move_ids):
        totals = {}
        for line in self.lines:
            if line.move_id not in tuple(move_ids):
                continue
            key = (line.move_id, line.account_id)
            debit, credit = totals.get(key, (0.0, 0.0))
            totals[key] = (debit + line.debit, credit + line.credit)
        return tuple(
            MoveAccountSumDTO(move_id, account_id, debit, credit)
            for (move_id, account_id), (debit, credit) in sorted(totals.items())
        )

    # -- reconciliation ------------------------------------------------
    def get_reconciled_after(self, line_ids, date_to):
        return {line_id: amount
                for line_id, amount in self.reconciled_after.items()
                if line_id in tuple(line_ids)}

    # -- internals -----------------------------------------------------
    def _select(self, ledger_filter, date_from, date_to, account_ids,
                company_ids):
        companies = tuple(company_ids or ledger_filter.company_ids)
        accounts = (tuple(account_ids) if account_ids is not None
                    else tuple(ledger_filter.account_ids))
        for line in self.lines:
            if line.company_id not in companies:
                continue
            if ledger_filter.posted_only and line.state != 'posted':
                continue
            if line.state == 'cancel':
                continue
            if date_from and line.date < date_from:
                continue
            if line.date > date_to:
                continue
            if accounts and line.account_id not in accounts:
                continue
            if (ledger_filter.partner_ids
                    and line.partner_id not in ledger_filter.partner_ids):
                continue
            if (ledger_filter.journal_ids
                    and line.journal_id not in ledger_filter.journal_ids):
                continue
            if (ledger_filter.product_ids
                    and line.product_id not in ledger_filter.product_ids):
                continue
            yield line
