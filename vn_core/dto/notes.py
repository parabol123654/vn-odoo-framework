# -*- coding: utf-8 -*-
"""DTOs for the figures in the notes to the financial statements (B09)."""

from typing import NamedTuple, Optional, Tuple


class NoteRowDTO(NamedTuple):
    """One row of a numeric table in the notes.

    Reads the ledger like a statement line (``expression``, ``side``,
    ``sign``, ``split_by_partner``, ``movement_side``) or totals other rows
    (``formula``). A row with neither is filled in by hand.
    """

    code: str
    expression: str = ''
    formula: str = ''
    sign: int = 1
    side: str = 'both'              # both | debit_only | credit_only
    split_by_partner: bool = False
    movement_side: str = 'net'      # net | debit | credit


class NoteTableDTO(NamedTuple):
    """A numeric table, and which kind of columns it carries.

    ``balance``: closing balance, with the opening balance as comparative
    (B09-DNN V.1 "Cuối năm / Đầu năm"). ``period``: the year's movement, with
    the previous year's as comparative (VI.1 "Năm nay / Năm trước").
    ``movement``: opening, increase, decrease and closing (V.5 fixed assets,
    V.10 taxes, V.13 equity).
    """

    code: str
    layout: str                     # balance | period | movement
    rows: Tuple[NoteRowDTO, ...] = ()
    #: Accounts of the year-end transfer, left out of a 'period' table the
    #: way they are left out of the income statement.
    closing_expression: str = ''


class NoteRowValueDTO(NamedTuple):
    """What the ledger says for one row.

    ``current`` is the closing balance, or the year's movement for a
    'period' table. ``opening`` is the balance the day before the year
    starts, or the previous year's movement for a 'period' table: the
    comparative a note falls back to when there is no earlier note to copy
    it from. ``increase`` and ``decrease`` only exist in a 'movement' table.
    """

    code: str
    current: float = 0.0
    opening: Optional[float] = None
    increase: Optional[float] = None
    decrease: Optional[float] = None
