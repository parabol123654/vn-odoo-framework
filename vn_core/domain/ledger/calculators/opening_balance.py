# -*- coding: utf-8 -*-
"""Opening balance calculator (Part 4 §9).

This module owns the single most error-prone rule in VAS reporting:

* A **balance-sheet** account's opening balance accumulates from inception.
* A **P&L** account's opening balance resets at the start of the fiscal year.

Getting it wrong makes last year's revenue leak into this year's Bảng cân đối
phát sinh. Because the rule is business logic it lives here, not in SQL: the
calculator emits the date windows to query, the Engine passes them to the
Repository, and the Repository stays a dumb aggregator.

No database access, no Odoo import — fully unit-testable.
"""

from typing import NamedTuple, Optional, Tuple
from datetime import date

from ....core.utils.dates import day_before, fiscal_year_start


class OpeningWindow(NamedTuple):
    """One aggregate query the Engine must ask the Repository for."""

    company_ids: Tuple[int, ...]
    account_ids: Tuple[int, ...]
    date_from: Optional[date]   # None -> from inception
    date_to: date


class OpeningBalanceCalculator:

    @staticmethod
    def windows(companies, accounts, date_from):
        """Return the minimal set of windows covering the opening balance.

        Balance-sheet accounts collapse into a single inception-to-date window
        regardless of company. P&L accounts are grouped by fiscal-year start, so
        companies sharing a fiscal year share one query. A single-company SME on
        a calendar year therefore costs two queries, not one per account.
        """
        if date_from is None:
            return ()

        cutoff = day_before(date_from)
        company_ids = tuple(c.id for c in companies)

        bs_accounts = tuple(a.id for a in accounts if a.include_initial_balance)
        pl_accounts = tuple(a.id for a in accounts if not a.include_initial_balance)

        windows = []
        if bs_accounts:
            windows.append(OpeningWindow(company_ids, bs_accounts, None, cutoff))

        if pl_accounts:
            by_year_start = {}
            for company in companies:
                start = fiscal_year_start(date_from,
                                          company.fiscalyear_last_day,
                                          company.fiscalyear_last_month)
                by_year_start.setdefault(start, []).append(company.id)
            for start, ids in sorted(by_year_start.items()):
                # An entry dated on or after date_from is not "opening"; if the
                # fiscal year starts at date_from the window is empty.
                if start > cutoff:
                    continue
                windows.append(
                    OpeningWindow(tuple(ids), pl_accounts, start, cutoff))

        return tuple(windows)

    @staticmethod
    def merge(aggregates):
        """Combine the per-window aggregate dicts into one.

        ``aggregates`` is an iterable of ``Dict[key, BalanceDTO]``. Windows never
        overlap by construction, but summing rather than overwriting keeps the
        calculator correct if a caller supplies overlapping windows.
        """
        merged = {}
        for chunk in aggregates:
            for key, amount in chunk.items():
                if key in merged:
                    merged[key] = merged[key].plus(amount)
                else:
                    merged[key] = amount
        return merged
