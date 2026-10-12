# -*- coding: utf-8 -*-
"""Ledger DTOs (Part 4 §14, Part 10 §7)."""

from datetime import date
from typing import NamedTuple, Optional, Tuple

from .common import CurrencyDTO


class MoveLineDTO(NamedTuple):
    """A journal item as returned by the Repository.

    This is the highest-cardinality DTO in the framework — one instance per
    ``account.move.line`` — so it stays a flat NamedTuple with no derived
    fields. Anything computed belongs in ``LedgerLineDTO``.
    """

    id: int
    date: date
    account_id: int
    journal_id: int
    move_id: int
    move_name: str
    debit: float
    credit: float
    balance: float
    label: str = ''
    ref: str = ''
    partner_id: Optional[int] = None
    analytic_account_id: Optional[int] = None
    currency_id: Optional[int] = None
    amount_currency: float = 0.0
    date_maturity: Optional[date] = None
    amount_residual: float = 0.0
    full_reconcile_id: Optional[int] = None
    company_id: Optional[int] = None
    state: str = 'posted'
    #: Số hiệu Phiếu thu / Phiếu chi, khi bút toán là một phiếu quỹ. Mẫu S07-DN
    #: yêu cầu số phiếu chứ không phải số bút toán.
    voucher_number: str = ''
    #: Sản phẩm và số lượng của dòng, khi bút toán sinh từ hoá đơn. Sổ chi
    #: tiết bán hàng (S35-DN) theo dõi doanh thu theo sản phẩm nên cần chúng;
    #: mọi báo cáo khác bỏ qua.
    product_id: Optional[int] = None
    quantity: float = 0.0

    @property
    def document_number(self):
        """What the statutory books print in the "Số hiệu chứng từ" column."""
        return self.voucher_number or self.move_name


class MoveAccountSumDTO(NamedTuple):
    """Per-move, per-account totals. Input to the counterpart calculator.

    The Repository returns raw sums only; deciding which accounts sit on which
    side of the entry is business logic and belongs to the calculator.
    """

    move_id: int
    account_id: int
    debit: float
    credit: float


class BalanceDTO(NamedTuple):
    """A debit/credit/net triple."""

    debit: float = 0.0
    credit: float = 0.0
    balance: float = 0.0

    def plus(self, other):
        return BalanceDTO(self.debit + other.debit,
                          self.credit + other.credit,
                          self.balance + other.balance)


class SidedBalanceDTO(NamedTuple):
    """A net balance presented one-sided, as VAS forms require.

    "Số dư đầu kỳ" and "Số dư cuối kỳ" appear as a single Nợ *or* Có figure,
    whereas "Phát sinh trong kỳ" is shown gross. Both presentations are carried
    so no report has to re-derive either.
    """

    balance: float = 0.0
    debit_balance: float = 0.0
    credit_balance: float = 0.0


class BalanceSummaryDTO(NamedTuple):
    """Opening, movement and closing for one aggregation key.

    The lightweight output of ``LedgerEngine.compute_balances``: everything a
    financial statement needs, without loading a single journal item.
    """

    opening: float = 0.0
    movement: BalanceDTO = BalanceDTO()
    closing: float = 0.0

    @property
    def debit_balance(self):
        return self.closing if self.closing > 0 else 0.0

    @property
    def credit_balance(self):
        return -self.closing if self.closing < 0 else 0.0


class LedgerLineDTO(NamedTuple):
    """A ledger line ready to render.

    ``account_code`` / ``account_name`` are resolved by the Engine from the
    account catalogue it already holds, costing no extra query and adding
    nothing to the far more numerous ``MoveLineDTO``. Part 4 §14 lists the
    account among the fields of the line DTO, and Sổ Nhật ký chung needs it:
    that book is ungrouped, so the account cannot be read off a group header.
    """

    source: MoveLineDTO
    running_balance: float = 0.0
    counterpart_account_ids: Tuple[int, ...] = ()
    counterpart_label: str = ''
    account_code: str = ''
    account_name: str = ''

    # Convenience passthroughs so templates never reach into ``source``.
    @property
    def date(self):
        return self.source.date

    @property
    def move_name(self):
        return self.source.document_number

    @property
    def label(self):
        return self.source.label

    @property
    def debit(self):
        return self.source.debit

    @property
    def credit(self):
        return self.source.credit

    @property
    def account_label(self):
        return ('%s - %s' % (self.account_code, self.account_name)
                if self.account_code else self.account_name)


class LedgerGroupDTO(NamedTuple):
    """One account / partner / journal block of a ledger report."""

    key: Tuple
    code: str
    name: str
    opening: SidedBalanceDTO
    movement: BalanceDTO
    closing: SidedBalanceDTO
    lines: Tuple[LedgerLineDTO, ...] = ()

    @property
    def display_name(self):
        return '%s - %s' % (self.code, self.name) if self.code else self.name


class LedgerDTO(NamedTuple):
    """Output of ``LedgerEngine.compute_ledger``."""

    groups: Tuple[LedgerGroupDTO, ...]
    totals: BalanceDTO
    currency: CurrencyDTO
    group_by: Tuple[str, ...] = ()


class ExpenseLedgerLineDTO(NamedTuple):
    """One debit row of the Sổ chi phí sản xuất, kinh doanh (S36-DN).

    ``amounts`` is aligned with the group's ``columns`` — the "chia ra" cells —
    and sums to the line's debit. Exactly one cell is non-zero: a line whose
    counterparts span several roots is not split by guesswork, it goes whole
    into the residual column (see the engine).
    """

    source: LedgerLineDTO
    amounts: Tuple[float, ...] = ()

    @property
    def date(self):
        return self.source.date

    @property
    def move_name(self):
        return self.source.move_name

    @property
    def label(self):
        return self.source.label

    @property
    def counterpart_label(self):
        return self.source.counterpart_label

    @property
    def debit(self):
        return self.source.debit

    @property
    def move_id(self):
        return self.source.source.move_id


class ExpenseLedgerGroupDTO(NamedTuple):
    """One account of the expense ledger — one S36-DN page.

    ``columns`` are counterpart account roots (``'152'``, ``'334'``, ...); the
    empty string is the residual column for whatever did not earn a column of
    its own. The Domain carries codes only — the label the residual column
    prints is the presentation layer's business.
    """

    account_id: int
    code: str
    name: str
    opening: SidedBalanceDTO
    columns: Tuple[str, ...]
    lines: Tuple[ExpenseLedgerLineDTO, ...]
    debit_total: float
    column_totals: Tuple[float, ...]
    #: "Ghi Có TK ..." — the period's credit in one figure. S36-DN details the
    #: debit side; the credit side is the closing transfer and prints as a
    #: single row.
    credit_total: float
    closing: SidedBalanceDTO

    @property
    def display_name(self):
        return '%s - %s' % (self.code, self.name) if self.code else self.name


class ExpenseLedgerDTO(NamedTuple):
    """Output of ``LedgerEngine.compute_expense_ledger``."""

    groups: Tuple[ExpenseLedgerGroupDTO, ...]
    total_debit: float
    total_credit: float
    currency: CurrencyDTO


class SalesLedgerLineDTO(NamedTuple):
    """One row of the Sổ chi tiết bán hàng (S35-DN).

    A line is either revenue (net credit on the 511 side) or a deduction (net
    debit on the 521 side) — the classification is the account root's, made in
    the engine. Closing transfers to 911 never reach this DTO.
    """

    source: LedgerLineDTO
    revenue: float = 0.0
    deduction: float = 0.0

    @property
    def date(self):
        return self.source.date

    @property
    def move_name(self):
        return self.source.move_name

    @property
    def label(self):
        return self.source.label

    @property
    def counterpart_label(self):
        return self.source.counterpart_label

    @property
    def account_code(self):
        return self.source.account_code

    @property
    def quantity(self):
        return self.source.source.quantity

    @property
    def unit_price(self):
        """Doanh thu chia số lượng — the price the ledger actually saw."""
        if not self.quantity or not self.revenue:
            return 0.0
        return self.revenue / self.quantity


class SalesLedgerGroupDTO(NamedTuple):
    """One product block of the sales ledger.

    ``product`` is None for revenue lines that carry no product — hand-written
    entries, mainly. They are grouped rather than hidden: a book that silently
    drops recorded revenue is how a total stops reconciling to account 511.
    """

    product: Optional[object]      # ProductDTO from dto.inventory, or None
    lines: Tuple[SalesLedgerLineDTO, ...]
    quantity_total: float = 0.0
    revenue_total: float = 0.0
    deduction_total: float = 0.0

    @property
    def net_revenue(self):
        return self.revenue_total - self.deduction_total

    @property
    def display_name(self):
        return self.product.display_name if self.product else ''


class SalesLedgerDTO(NamedTuple):
    groups: Tuple[SalesLedgerGroupDTO, ...]
    total_revenue: float
    total_deduction: float
    currency: CurrencyDTO

    @property
    def total_net_revenue(self):
        return self.total_revenue - self.total_deduction


class AllocationRowDTO(NamedTuple):
    """One "đối tượng sử dụng" row of the Bảng phân bổ NVL, CCDC (07-VT).

    ``code`` is the debit-side account root the materials went to (``621``,
    ``641``, ``632``...); the empty string is the residual row for entries
    whose debit side spans several roots — they are not split by guesswork,
    same rule as the expense ledger. ``amounts`` aligns with the table's
    ``columns``.
    """

    code: str
    amounts: Tuple[float, ...] = ()
    total: float = 0.0


class AllocationTableDTO(NamedTuple):
    """Output of ``LedgerEngine.compute_allocation_table``.

    ``columns`` are the credited account roots — the "Ghi Có TK" of the form:
    152, 153, 242. A period table only: 07-VT is a chứng từ phân bổ, it
    carries no balances.
    """

    columns: Tuple[str, ...]
    rows: Tuple[AllocationRowDTO, ...]
    column_totals: Tuple[float, ...]
    grand_total: float
    currency: CurrencyDTO


class TrialBalanceRowDTO(NamedTuple):
    """One line of a Bảng cân đối phát sinh."""

    account_id: int
    code: str
    name: str
    opening: SidedBalanceDTO
    opening_gross: BalanceDTO
    movement: BalanceDTO
    closing: SidedBalanceDTO


class TrialBalanceDTO(NamedTuple):
    rows: Tuple[TrialBalanceRowDTO, ...]
    total_opening: SidedBalanceDTO
    total_movement: BalanceDTO
    total_closing: SidedBalanceDTO
    currency: CurrencyDTO
    is_balanced: bool = True


# ----------------------------------------------------------------------
# Aged receivable / payable
# ----------------------------------------------------------------------

class AgingBucketDTO(NamedTuple):
    """One ageing column.

    ``upper`` is the inclusive upper bound in days; ``None`` means "and older",
    so the last bucket is open-ended. ``lower`` of ``None`` marks the not-yet-due
    column, which VAS forms print as "Trong hạn".
    """

    label: str
    lower: Optional[int]
    upper: Optional[int]

    @property
    def is_current(self):
        return self.lower is None


class AgingLineDTO(NamedTuple):
    """One open item, with the bucket it fell into."""

    source: MoveLineDTO
    residual: float
    days_overdue: int
    bucket_index: int
    account_code: str = ''
    account_name: str = ''

    @property
    def date(self):
        return self.source.date

    @property
    def due_date(self):
        return self.source.date_maturity or self.source.date

    @property
    def move_name(self):
        return self.source.document_number

    @property
    def label(self):
        return self.source.label


class AgingGroupDTO(NamedTuple):
    """All open items of one partner."""

    partner_id: Optional[int]
    partner_name: str
    lines: Tuple[AgingLineDTO, ...]
    amounts: Tuple[float, ...]      # one figure per bucket, aligned to buckets
    total: float = 0.0


class AgingDTO(NamedTuple):
    buckets: Tuple[AgingBucketDTO, ...]
    groups: Tuple[AgingGroupDTO, ...]
    totals: Tuple[float, ...]
    grand_total: float
    currency: CurrencyDTO
    as_of: Optional[object] = None
