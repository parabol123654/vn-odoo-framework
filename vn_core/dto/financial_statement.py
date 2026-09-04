# -*- coding: utf-8 -*-
"""Financial statement DTOs (Part 5 §12, Part 9 §5-6)."""

from typing import NamedTuple, Optional, Tuple

from .common import CompanyDTO, CurrencyDTO


class MappingLineDTO(NamedTuple):
    """One row of a statutory form.

    ``expression`` selects accounts (``111*,112*,-1113``). ``formula`` instead
    references other line codes (``10-11``). A line uses one or the other; a
    line with neither is a pure heading.

    ``side`` and ``split_by_partner`` exist because a Vietnamese balance sheet
    cannot be produced without them. Item "Phải thu ngắn hạn của khách hàng"
    takes only the debit side of 131 and "Người mua trả tiền trước" only the
    credit side, and both are evaluated **per partner** before being summed —
    netting the account first gives a number that is simply wrong.
    """

    code: str
    name: str
    sequence: int = 0
    level: int = 0
    parent_code: str = ''
    expression: str = ''
    formula: str = ''
    sign: int = 1
    side: str = 'both'              # both | debit_only | credit_only
    split_by_partner: bool = False
    note_ref: str = ''              # "Thuyết minh" column
    visible: bool = True
    bold: bool = False


class MappingDTO(NamedTuple):
    code: str
    name: str
    report_type: str                # balance_sheet | income_statement | cash_flow
    basis: str                      # closing | movement
    version: str = 'TT200'
    #: Equality the finished statement must satisfy, e.g. "270=440".
    balance_check: str = ''
    #: Which accounts count as cash. Only meaningful for a cash flow statement.
    cash_expression: str = ''
    #: 'direct' or 'indirect'. Decides which engine builds the statement.
    cash_flow_method: str = 'direct'
    lines: Tuple[MappingLineDTO, ...] = ()


class FinancialStatementLineDTO(NamedTuple):
    code: str
    name: str
    amount: float = 0.0
    previous_amount: Optional[float] = None
    level: int = 0
    sequence: int = 0
    parent_code: str = ''
    note_ref: str = ''
    bold: bool = False
    is_computed: bool = False       # True when produced by a formula
    #: Accounts the figure is built from, resolved transitively through
    #: formulas. Empty for a heading or a line the ledger cannot explain.
    account_ids: Tuple[int, ...] = ()


class UnmappedAccountDTO(NamedTuple):
    """An account carrying a balance that no statement line picks up.

    A balance sheet that silently omits an account still prints, still looks
    plausible, and is wrong. Rather than hope the mapping is complete, the
    engine reports what it did not cover.
    """

    id: int
    code: str
    name: str
    balance: float


class BalanceCheckDTO(NamedTuple):
    """The equality a statement must satisfy, e.g. 270 = 440."""

    left_code: str
    right_code: str
    left_amount: float = 0.0
    right_amount: float = 0.0
    difference: float = 0.0
    is_balanced: bool = True


class FinancialStatementDTO(NamedTuple):
    mapping_code: str
    report_name: str
    report_type: str
    version: str
    company: CompanyDTO
    currency: CurrencyDTO
    lines: Tuple[FinancialStatementLineDTO, ...] = ()
    date_from: Optional[object] = None
    date_to: Optional[object] = None
    comparative: bool = False
    balance_check: Optional[BalanceCheckDTO] = None
    unmapped: Tuple[UnmappedAccountDTO, ...] = ()

    def by_code(self, code):
        for line in self.lines:
            if line.code == code:
                return line
        return None
