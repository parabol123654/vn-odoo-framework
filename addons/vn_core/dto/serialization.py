# -*- coding: utf-8 -*-
"""DTO serialization (Part 10 §16).

Turns the nested NamedTuple DTOs into JSON-safe primitives for the JSON renderer
and the web client. Pure Python: the Domain stays free of Odoo, and the same
function works in a unit test with no registry.
"""

import datetime
from enum import Enum


def to_primitive(value):
    """Recursively convert DTOs, dates and enums into JSON-safe values."""
    # NamedTuple before tuple: _asdict() keeps the field names.
    if hasattr(value, '_asdict'):
        return {key: to_primitive(item)
                for key, item in value._asdict().items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime.datetime,)):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_primitive(item) for item in value]
    return value
