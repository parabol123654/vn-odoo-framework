# -*- coding: utf-8 -*-
"""Counterpart account calculator (Part 4 §12).

Odoo stores no notion of a counterpart account, so it is derived from the other
lines of the same journal entry. Deciding which accounts sit on which side is
business logic, which is why the Repository returns raw per-account sums and
this calculator interprets them.

Exact for a two-line entry. For a multi-line entry every account on the opposite
side is returned with **no amount allocation** — the caller must not assume a
one-to-one relationship. The direct-method cash flow statement needs an explicit
allocation rule layered on top of this.
"""


class CounterpartCalculator:

    @staticmethod
    def index(move_account_sums):
        """Group raw sums into ``{move_id: (debit_accounts, credit_accounts)}``."""
        sides = {}
        for row in move_account_sums:
            debit_ids, credit_ids = sides.setdefault(row.move_id, ([], []))
            if row.debit > row.credit:
                debit_ids.append(row.account_id)
            elif row.credit > row.debit:
                credit_ids.append(row.account_id)
        return {move_id: (tuple(d), tuple(c))
                for move_id, (d, c) in sides.items()}

    @staticmethod
    def for_line(line, index):
        """Accounts facing ``line`` inside its own entry."""
        entry = index.get(line.move_id)
        if not entry:
            return ()
        debit_ids, credit_ids = entry
        opposite = credit_ids if line.debit > line.credit else debit_ids
        return tuple(a for a in opposite if a != line.account_id)
