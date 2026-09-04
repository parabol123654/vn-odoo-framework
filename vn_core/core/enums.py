# -*- coding: utf-8 -*-
"""Domain enumerations. Pure Python."""

from enum import Enum


class TargetMove(Enum):
    POSTED = 'posted'
    ALL = 'all'


class GroupBy(Enum):
    """Aggregation dimensions supported by the Ledger Domain (Part 4 §13).

    ``fields`` is the ordered tuple of ``MoveLineDTO`` attribute names that
    form the group key. The Engine never hardcodes these tuples.
    """

    NONE = ()
    ACCOUNT = ('account_id',)
    PARTNER = ('partner_id',)
    JOURNAL = ('journal_id',)
    ANALYTIC = ('analytic_account_id',)
    ACCOUNT_PARTNER = ('account_id', 'partner_id')
    PARTNER_ACCOUNT = ('partner_id', 'account_id')

    @property
    def fields(self):
        return self.value


class BalanceSide(Enum):
    """Which side of a net balance a report item consumes.

    Needed by the Balance Sheet: item "Phải thu khách hàng" takes only the
    debit side of 131 and "Người mua trả tiền trước" only the credit side,
    each evaluated per partner before aggregation.
    """

    BOTH = 'both'
    DEBIT_ONLY = 'debit_only'
    CREDIT_ONLY = 'credit_only'


class AgingBasis(Enum):
    """Which date an open item is aged from.

    Vietnamese practice splits: analysts age from the due date to measure
    overdue risk, while many SMEs age from the document date because their
    contracts have no explicit payment term. Both are offered rather than one
    being imposed.
    """

    DUE_DATE = 'due_date'
    DOCUMENT_DATE = 'document_date'


class AgingSide(Enum):
    """Receivable or payable, i.e. which sign of residual is kept."""

    RECEIVABLE = 'receivable'
    PAYABLE = 'payable'


class TaxDirection(Enum):
    """Which side of VAT a listing covers.

    Vietnamese filings keep the two apart: Bảng kê hoá đơn hàng hoá dịch vụ bán
    ra (output VAT, account 3331) and mua vào (input VAT, account 133). They are
    never mixed on one form.
    """

    SALE = 'sale'
    PURCHASE = 'purchase'
