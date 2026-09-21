# -*- coding: utf-8 -*-
"""Date helpers, including fiscal-year arithmetic.

The fiscal-year rule matters for opening balances: a P&L account's opening
balance resets at the start of its company's fiscal year, while a balance-sheet
account accumulates from inception. That rule is business logic, so it lives in
the Domain rather than in ``res.company.compute_fiscalyear_dates``.
"""

import calendar
from datetime import date, timedelta


def _clamped(year, month, day):
    """Build a date, clamping ``day`` to the last day of that month."""
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def fiscal_year_end(date_ref, last_day=31, last_month=12):
    """Last day of the fiscal year containing ``date_ref``."""
    candidate = _clamped(date_ref.year, last_month, last_day)
    if date_ref <= candidate:
        return candidate
    return _clamped(date_ref.year + 1, last_month, last_day)


def fiscal_year_start(date_ref, last_day=31, last_month=12):
    """First day of the fiscal year containing ``date_ref``."""
    end = fiscal_year_end(date_ref, last_day, last_month)
    previous = _clamped(end.year - 1, end.month, end.day)
    return previous + timedelta(days=1)


def day_before(value):
    return value - timedelta(days=1)
