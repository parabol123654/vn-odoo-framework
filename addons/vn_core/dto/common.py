# -*- coding: utf-8 -*-
"""Common DTOs (Part 10 §12).

These carry every piece of Odoo metadata the Domain needs, so that no engine or
calculator ever has to reach for ``env``. In particular:

* ``CurrencyDTO.rounding`` replaces ``currency.round()``.
* ``CompanyDTO.fiscalyear_last_day/month`` replaces
  ``company.compute_fiscalyear_dates()``.
* ``AccountDTO.include_initial_balance`` replaces
  ``account.user_type_id.include_initial_balance``.

``NamedTuple`` is used rather than a frozen dataclass: it is immutable, it
serialises with ``_asdict()``, and on Python 3.8 it is the only stdlib option
that is both immutable and slot-based — which matters because ``MoveLineDTO`` is
instantiated once per journal item.
"""

from typing import NamedTuple, Optional


class CurrencyDTO(NamedTuple):
    id: int
    name: str
    rounding: float = 0.01
    decimal_places: int = 2


class CompanyDTO(NamedTuple):
    id: int
    name: str
    currency: CurrencyDTO
    fiscalyear_last_day: int = 31
    fiscalyear_last_month: int = 12


class AccountDTO(NamedTuple):
    id: int
    code: str
    name: str
    # True for balance-sheet accounts, False for P&L accounts. Drives whether
    # the opening balance accumulates from inception or resets each year.
    include_initial_balance: bool = True
    internal_group: str = ''

    @property
    def display_name(self):
        return '%s - %s' % (self.code, self.name) if self.code else self.name


class PartnerDTO(NamedTuple):
    id: int
    name: str
    ref: str = ''

    @property
    def display_name(self):
        return self.name


class JournalDTO(NamedTuple):
    id: int
    code: str
    name: str

    @property
    def display_name(self):
        return '%s - %s' % (self.code, self.name) if self.code else self.name


class AnalyticAccountDTO(NamedTuple):
    id: int
    code: str
    name: str

    @property
    def display_name(self):
        return '%s - %s' % (self.code, self.name) if self.code else self.name


class ReportMetadataDTO(NamedTuple):
    """Header metadata every ReportDTO must carry (Part 10 §15)."""

    report_name: str
    company: CompanyDTO
    printed_at: str
    printed_by: str = ''
    date_from: Optional[object] = None
    date_to: Optional[object] = None
    version: str = ''
