# -*- coding: utf-8 -*-
"""Tax DTOs (Part 10 §10).

The unit of a Vietnamese VAT listing is the **invoice**, not the journal item.
An invoice with five product lines is one row on the Bảng kê, so ``TaxLineDTO``
already represents an invoice-and-rate pair rather than a raw ledger line.
"""

from datetime import date
from typing import NamedTuple, Optional, Tuple

from .common import CurrencyDTO


class TaxLineDTO(NamedTuple):
    move_id: int
    move_name: str
    invoice_number: str
    invoice_date: date
    partner_name: str
    partner_vat: str
    tax_id: int
    tax_name: str
    tax_rate: float                 # phần trăm, ví dụ 10.0
    base_amount: float
    tax_amount: float
    move_type: str = 'entry'
    partner_id: Optional[int] = None
    account_code: str = ''

    @property
    def is_refund(self):
        return self.move_type in ('out_refund', 'in_refund')


class TaxRateGroupDTO(NamedTuple):
    """One thuế suất block of the listing."""

    rate: float
    label: str
    lines: Tuple[TaxLineDTO, ...] = ()
    base_total: float = 0.0
    tax_total: float = 0.0


class VatListingDTO(NamedTuple):
    direction: str                  # sale | purchase
    groups: Tuple[TaxRateGroupDTO, ...]
    base_total: float
    tax_total: float
    currency: CurrencyDTO
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    invoice_count: int = 0


class VatDeclarationInputDTO(NamedTuple):
    """Figures the ledger cannot supply, so the accountant must.

    Carried-forward credit comes from the previous period's own declaration,
    which this framework does not store; the adjustments and the refund claim
    are decisions, not derivations. Asking for them is more honest than
    defaulting them to zero and letting the form look complete.
    """

    carried_forward: float = 0.0        # chỉ tiêu 22
    adjustment_decrease: float = 0.0    # chỉ tiêu 37
    adjustment_increase: float = 0.0    # chỉ tiêu 38
    refund_claimed: float = 0.0         # chỉ tiêu 42
