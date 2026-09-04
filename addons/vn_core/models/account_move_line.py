# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Indexing support for ledger reporting.

Every ledger query filters on ``company_id`` + ``parent_state`` + ``date`` and
then groups by account or partner. Odoo 14 indexes some of those columns
individually but not in combination, and a furniture SME's yearly General Ledger
reaches several hundred thousand journal items.

This is the one legitimate reason for a model in the framework: it changes the
shape of an existing table rather than adding business logic.
"""

from odoo import models
from odoo.tools.sql import create_index


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def init(self):
        parent_init = getattr(super(), 'init', None)
        if parent_init:
            parent_init()
        create_index(
            self._cr,
            'account_move_line_vn_ledger_idx',
            self._table,
            ['company_id', 'parent_state', 'date', 'account_id'],
        )
        create_index(
            self._cr,
            'account_move_line_vn_partner_idx',
            self._table,
            ['company_id', 'parent_state', 'date', 'partner_id'],
        )
