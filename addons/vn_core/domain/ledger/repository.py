# -*- coding: utf-8 -*-
"""Ledger Repository interface (Part 4 §8, Part 6 §6).

The Engine knows this contract and nothing else. It has no idea whether the
implementation uses the ORM, raw SQL, a snapshot table or an in-memory fake —
which is what makes the Engine unit-testable without a database.

Implementations must return DTOs, never recordsets, and must contain no
business logic: no opening-balance rule, no side detection, no sign handling.
"""

import abc


class ILedgerRepository(abc.ABC):

    # -- reference data ------------------------------------------------
    @abc.abstractmethod
    def get_companies(self, company_ids):
        """-> Tuple[CompanyDTO, ...] including currency and fiscal year."""

    @abc.abstractmethod
    def get_accounts(self, ledger_filter):
        """-> Tuple[AccountDTO, ...] in scope for the filter."""

    @abc.abstractmethod
    def get_partners(self, partner_ids):
        """-> Tuple[PartnerDTO, ...]"""

    @abc.abstractmethod
    def get_products(self, product_ids):
        """-> Tuple[ProductDTO, ...] — for the sales ledger's grouping."""

    @abc.abstractmethod
    def get_journals(self, journal_ids):
        """-> Tuple[JournalDTO, ...]"""

    @abc.abstractmethod
    def get_analytic_accounts(self, analytic_ids):
        """-> Tuple[AnalyticAccountDTO, ...]"""

    # -- aggregates ----------------------------------------------------
    @abc.abstractmethod
    def aggregate_balances(self, ledger_filter, group_by, date_from, date_to,
                           account_ids=None, company_ids=None):
        """Sum debit/credit/balance over an explicit date window.

        The window is supplied by the caller precisely so that the repository
        needs no knowledge of the fiscal-year rule. ``date_from=None`` means
        "from inception".

        -> Dict[Tuple, BalanceDTO] keyed by the ``group_by`` field values.
        """

    # -- detail --------------------------------------------------------
    @abc.abstractmethod
    def get_move_lines(self, ledger_filter):
        """-> Iterable[MoveLineDTO] ordered by date, move, id."""

    @abc.abstractmethod
    def get_move_account_sums(self, move_ids):
        """-> Tuple[MoveAccountSumDTO, ...] for counterpart detection."""

    # -- reconciliation ------------------------------------------------
    @abc.abstractmethod
    def get_reconciled_after(self, line_ids, date_to):
        """Amounts matched against ``line_ids`` strictly after ``date_to``.

        -> Dict[int, float] to be added back to ``amount_residual`` when aging
        a balance as at a past date.
        """
