# -*- coding: utf-8 -*-
"""Tax repository interface (Part 6 §12).

Returns one row per **invoice and tax rate**, already aggregated. Doing that
aggregation in SQL rather than in the Engine matters: a Vietnamese SME files
several thousand invoices a quarter, and pulling every product line back only to
group it in Python would be wasteful.

The repository applies no sign convention and makes no judgement about which
side of VAT a row belongs to. That is business logic and lives in the Engine.
"""

import abc


class ITaxRepository(abc.ABC):

    @abc.abstractmethod
    def get_tax_lines(self, ledger_filter, direction):
        """-> Iterable[TaxLineDTO], one per (invoice, tax).

        ``direction`` is a ``TaxDirection``; the repository uses it only to pick
        which taxes are in scope, not to decide signs.
        """

    @abc.abstractmethod
    def get_currency(self, company_ids):
        """-> CurrencyDTO of the reporting company."""
