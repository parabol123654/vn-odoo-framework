# -*- coding: utf-8 -*-
"""Filter DTOs (Part 4 §5, Part 10 §6).

Every ledger report accepts exactly this object. No loose keyword arguments, no
dictionaries, no recordsets.
"""

from datetime import date
from typing import NamedTuple, Optional, Tuple

from ..core.enums import TargetMove


class LedgerFilter(NamedTuple):
    date_to: date
    company_ids: Tuple[int, ...]
    # None means "from inception", which is what an as-at balance sheet or an
    # aged balance needs.
    date_from: Optional[date] = None
    target_move: TargetMove = TargetMove.POSTED
    account_ids: Tuple[int, ...] = ()
    partner_ids: Tuple[int, ...] = ()
    journal_ids: Tuple[int, ...] = ()
    analytic_account_ids: Tuple[int, ...] = ()
    analytic_tag_ids: Tuple[int, ...] = ()
    account_type_ids: Tuple[int, ...] = ()
    #: Restricts to journal items carrying these products — what the Sổ chi
    #: tiết bán hàng filters by. Empty means no product restriction.
    product_ids: Tuple[int, ...] = ()
    currency_id: Optional[int] = None
    include_opening: bool = True
    include_closing: bool = True

    @property
    def posted_only(self):
        return self.target_move is TargetMove.POSTED

    def replace(self, **changes):
        """Return a new filter; the DTO itself stays immutable (Part 10 §17)."""
        return self._replace(**changes)


class InventoryFilter(NamedTuple):
    """The single filter every stock report accepts.

    ``date_from`` of ``None`` means "from inception", which is what an opening
    balance needs. Unlike the ledger there is no fiscal-year reset: stock is a
    balance-sheet quantity and always accumulates.
    """

    date_to: date
    company_ids: Tuple[int, ...]
    date_from: Optional[date] = None
    product_ids: Tuple[int, ...] = ()
    category_ids: Tuple[int, ...] = ()
    warehouse_ids: Tuple[int, ...] = ()
    location_ids: Tuple[int, ...] = ()

    def replace(self, **changes):
        return self._replace(**changes)


class AssetFilter(NamedTuple):
    """Filter for the fixed-asset reports.

    ``include_unposted`` widens the reports from the books to the plan: by
    default only depreciation that reached the ledger (or was declared as an
    initial balance) counts, which is what a statutory book prints.
    """

    date_to: date
    company_ids: Tuple[int, ...]
    date_from: Optional[date] = None
    asset_ids: Tuple[int, ...] = ()
    profile_ids: Tuple[int, ...] = ()
    include_unposted: bool = False

    def replace(self, **changes):
        return self._replace(**changes)


class ManufacturingFilter(NamedTuple):
    """Filter for production cost reporting.

    A manufacturing order is costed when it finishes, so the period selects on
    the completion date. Orders still open at ``date_to`` are reported
    separately as work in progress rather than being costed early.
    """

    date_to: date
    company_ids: Tuple[int, ...]
    date_from: Optional[date] = None
    product_ids: Tuple[int, ...] = ()
    category_ids: Tuple[int, ...] = ()
    production_ids: Tuple[int, ...] = ()
    include_open: bool = True

    def replace(self, **changes):
        return self._replace(**changes)
