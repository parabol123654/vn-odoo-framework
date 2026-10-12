# -*- coding: utf-8 -*-
"""Fixed-asset repository interface.

The asset reports read an asset **subledger** — per-asset records with their
own depreciation schedule — not the general ledger. On the Odoo side that
subledger is OCA ``account_asset_management``; this interface is what keeps
the Engine ignorant of that fact, and the in-memory fake in the tests is the
second implementation that keeps the interface honest.
"""

import abc


class IAssetRepository(abc.ABC):

    @abc.abstractmethod
    def get_profiles(self, asset_filter):
        """-> Tuple[AssetProfileDTO, ...] in scope for the filter."""

    @abc.abstractmethod
    def get_assets(self, asset_filter):
        """-> Tuple[AssetDTO, ...] in scope: company, profile and asset
        restrictions applied; draft assets excluded — they are not in the
        books. Date filtering is the Engine's business.
        """

    @abc.abstractmethod
    def get_lines(self, asset_ids, date_from=None, date_to=None):
        """-> Tuple[AssetLineDTO, ...] of the given assets, in date order.

        Every line type (create / depreciate / remove) and every posting state
        is returned within the optional inclusive bounds; the Engine decides
        what counts, because "the books versus the plan" is a business rule.
        """

    @abc.abstractmethod
    def get_currency(self, company_ids):
        """-> CurrencyDTO of the reporting company."""
