# -*- coding: utf-8 -*-
"""Numeric helpers.

Deliberately reimplemented instead of importing ``odoo.tools.float_round``, so
that the whole Domain layer stays importable — and unit-testable — without
Odoo on the path. Semantics mirror Odoo: round to the nearest multiple of the
currency's ``rounding`` unit, halves away from zero.
"""

from decimal import Decimal, ROUND_HALF_UP


def round_amount(value, rounding):
    """Round ``value`` to the nearest multiple of ``rounding``.

    ``rounding`` of 0 or None means "do not round" (mirrors Odoo).
    """
    if not rounding:
        return float(value)
    unit = Decimal(repr(float(rounding)))
    scaled = Decimal(repr(float(value))) / unit
    return float(scaled.quantize(Decimal('1'), rounding=ROUND_HALF_UP) * unit)


def is_zero(value, rounding):
    """True when ``value`` is zero at the given rounding precision."""
    if not rounding:
        return value == 0.0
    return round_amount(value, rounding) == 0.0


def compare(first, second, rounding):
    """Return -1, 0 or 1 comparing two amounts at the given precision."""
    delta = round_amount(first - second, rounding)
    if delta == 0.0:
        return 0
    return -1 if delta < 0 else 1
