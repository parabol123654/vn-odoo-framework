# -*- coding: utf-8 -*-
"""Fixed-asset DTOs.

The asset reports read the asset subledger — OCA ``account_asset_management``
on the Odoo side — but nothing here knows that: these are the shapes the
Engine computes with, and the fake repository in the tests is their second
producer, same as every other domain.

S21-DN asks for columns Odoo has no data for — nước sản xuất, năm sản xuất.
They are deliberately absent from the DTO rather than carried as always-empty
strings: the template prints the blank, and the docs say why.
"""

from datetime import date
from typing import NamedTuple, Optional, Tuple

from .common import CurrencyDTO


class AssetProfileDTO(NamedTuple):
    """A nhóm TSCĐ: the OCA asset profile."""

    id: int
    name: str
    asset_account_code: str = ''         # TK nguyên giá (211...)
    depreciation_account_code: str = ''  # TK hao mòn (214...)
    expense_account_code: str = ''       # TK chi phí khấu hao mặc định


class AssetDTO(NamedTuple):
    id: int
    name: str
    profile_id: int
    state: str                 # draft / open / close / removed
    purchase_value: float      # nguyên giá
    salvage_value: float = 0.0
    code: str = ''             # số hiệu TSCĐ
    date_start: Optional[date] = None
    date_remove: Optional[date] = None
    method: str = 'linear'
    method_number: int = 0     # số năm khấu hao
    method_period: str = 'year'
    #: Số hiệu chứng từ ghi tăng — the journal entry the asset was created
    #: from, when the subledger links one.
    acquisition_ref: str = ''

    @property
    def annual_rate(self):
        """Tỷ lệ khấu hao năm (%), derivable for the linear methods only.

        A degressive asset has no single rate; S21-DN's "tỷ lệ" column is
        printed only where it means something, so this returns 0 there and
        the annual amount column speaks instead.
        """
        if self.method in ('linear', 'linear-limit') and self.method_number:
            return 100.0 / self.method_number
        return 0.0

    @property
    def annual_amount(self):
        """Mức khấu hao năm under the linear methods, 0 otherwise."""
        if not (self.method in ('linear', 'linear-limit')
                and self.method_number):
            return 0.0
        base = (self.purchase_value if self.method == 'linear-limit'
                else self.purchase_value - self.salvage_value)
        return base / self.method_number

    @property
    def is_removed(self):
        return self.state == 'removed'


class AssetLineDTO(NamedTuple):
    """One row of an asset's depreciation table.

    ``counted`` is what separates the books from the plan: a line is counted
    when its journal entry exists, or when it is an initial-balance line the
    subledger deliberately posts no entry for. Everything else is a forecast.
    """

    id: int
    asset_id: int
    date: date
    amount: float
    line_type: str = 'depreciate'   # create / depreciate / remove
    posted: bool = False
    init: bool = False
    move_name: str = ''
    #: Code of the account the depreciation was charged to — read from the
    #: posted entry when there is one, the profile default otherwise.
    expense_code: str = ''

    @property
    def counted(self):
        return self.posted or self.init


class AssetRegisterRowDTO(NamedTuple):
    """One asset on the Sổ TSCĐ (S21-DN)."""

    asset: AssetDTO
    #: Khấu hao luỹ kế đã ghi sổ đến ngày báo cáo.
    accumulated: float = 0.0
    #: Giá trị còn lại theo sổ: nguyên giá − luỹ kế.
    residual: float = 0.0


class AssetRegisterGroupDTO(NamedTuple):
    """One nhóm TSCĐ block of the register."""

    profile: AssetProfileDTO
    rows: Tuple[AssetRegisterRowDTO, ...]
    total_purchase: float = 0.0
    total_accumulated: float = 0.0
    total_residual: float = 0.0


class AssetRegisterDTO(NamedTuple):
    groups: Tuple[AssetRegisterGroupDTO, ...]
    total_purchase: float
    total_accumulated: float
    total_residual: float
    currency: CurrencyDTO


class AssetCardYearDTO(NamedTuple):
    """One "giá trị hao mòn" year row of the Thẻ TSCĐ (S23-DN)."""

    year: int
    amount: float
    cumulative: float


class AssetCardDTO(NamedTuple):
    """One asset's card."""

    asset: AssetDTO
    profile: AssetProfileDTO
    years: Tuple[AssetCardYearDTO, ...]
    accumulated: float = 0.0
    residual: float = 0.0


class AssetCardsDTO(NamedTuple):
    cards: Tuple[AssetCardDTO, ...]
    currency: CurrencyDTO


class AllocationSummaryDTO(NamedTuple):
    """The I–IV summary of the Bảng tính và phân bổ khấu hao (06-TSCĐ).

    Each figure is measured directly, none derived from the others, so the
    identity I + II − III = IV holds only when nothing else changed — a
    recomputed board or a mid-life adjustment shows up as the imbalance
    instead of disappearing into a derived number.
    """

    previous_total: float = 0.0     # I.  Số KH đã trích kỳ trước
    increase: float = 0.0           # II. KH của TSCĐ tăng trong kỳ
    decrease: float = 0.0           # III. KH của TSCĐ giảm trong kỳ
    current_total: float = 0.0      # IV. Số KH phải trích kỳ này

    @property
    def imbalance(self):
        return (self.previous_total + self.increase
                - self.decrease - self.current_total)


class DepreciationAllocationRowDTO(NamedTuple):
    """One nhóm TSCĐ row of 06-TSCĐ, spread over the expense columns."""

    profile: AssetProfileDTO
    amounts: Tuple[float, ...]
    total: float = 0.0


class DepreciationAllocationDTO(NamedTuple):
    #: Expense-account roots the depreciation was charged to (627, 641, 642...).
    columns: Tuple[str, ...]
    rows: Tuple[DepreciationAllocationRowDTO, ...]
    column_totals: Tuple[float, ...]
    grand_total: float
    summary: AllocationSummaryDTO
    currency: CurrencyDTO
