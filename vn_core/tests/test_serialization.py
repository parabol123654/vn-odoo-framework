# -*- coding: utf-8 -*-
"""Serialization contract tests.

``to_primitive`` is what any JSON-facing consumer sees: the REST renderer
required by Part 7 §17, an external integration, or a cache entry. Those
consumers address fields by path, and a renamed DTO field would break them
silently rather than loudly. These tests pin the emitted shape.

The current web viewer renders HTML server-side and does not go through here, so
nothing in the UI depends on these paths today — that is exactly why they need a
test rather than being covered incidentally.
"""

import json
import unittest
from datetime import date

from ..core.enums import GroupBy
from ..domain.ledger.engine import LedgerEngine
from ..dto.common import AccountDTO, CompanyDTO, CurrencyDTO
from ..dto.filters import LedgerFilter
from ..dto.ledger import MoveLineDTO
from ..dto.serialization import to_primitive
from .fakes import FakeLedgerRepository

VND = CurrencyDTO(id=1, name='VND', rounding=1.0, decimal_places=0)
ACME = CompanyDTO(id=1, name='ACME Furniture', currency=VND)
ACCOUNTS = (
    AccountDTO(131, '131', 'Phải thu khách hàng', include_initial_balance=True),
    AccountDTO(511, '511', 'Doanh thu bán hàng', include_initial_balance=False),
)


def _entry(move_id, when, amount):
    return (
        MoveLineDTO(id=move_id * 10 + 1, date=when, account_id=131,
                    journal_id=1, move_id=move_id, move_name='INV/%s' % move_id,
                    debit=amount, credit=0.0, balance=amount, company_id=1,
                    label='Bán hàng'),
        MoveLineDTO(id=move_id * 10 + 2, date=when, account_id=511,
                    journal_id=1, move_id=move_id, move_name='INV/%s' % move_id,
                    debit=0.0, credit=amount, balance=-amount, company_id=1,
                    label='Bán hàng'),
    )


class TestSerialization(unittest.TestCase):

    def setUp(self):
        repo = FakeLedgerRepository(
            companies=(ACME,), accounts=ACCOUNTS,
            lines=_entry(1, date(2025, 12, 1), 200.0)
                  + _entry(2, date(2026, 1, 5), 100.0))
        self.engine = LedgerEngine(repo)
        self.filter = LedgerFilter(
            date_to=date(2026, 1, 31), date_from=date(2026, 1, 1),
            company_ids=(1,), account_ids=(131,))

    def test_ledger_payload_is_json_serialisable(self):
        payload = to_primitive(self.engine.compute_ledger(
            self.filter, group_by=GroupBy.ACCOUNT, with_counterpart=True))
        # Must survive an actual JSON round trip, not merely look like dicts.
        json.loads(json.dumps(payload))

    def test_ledger_payload_shape(self):
        payload = to_primitive(self.engine.compute_ledger(
            self.filter, group_by=GroupBy.ACCOUNT, with_counterpart=True))

        self.assertIn('groups', payload)
        self.assertIn('totals', payload)
        group = payload['groups'][0]
        for key in ('code', 'name', 'opening', 'movement', 'closing', 'lines'):
            self.assertIn(key, group)
        for key in ('balance', 'debit_balance', 'credit_balance'):
            self.assertIn(key, group['opening'])
            self.assertIn(key, group['closing'])
        for key in ('debit', 'credit', 'balance'):
            self.assertIn(key, group['movement'])
            self.assertIn(key, payload['totals'])

        line = group['lines'][0]
        for key in ('source', 'running_balance', 'counterpart_account_ids',
                    'counterpart_label'):
            self.assertIn(key, line)
        for key in ('date', 'move_id', 'move_name', 'label', 'debit', 'credit'):
            self.assertIn(key, line['source'])

    def test_dates_become_iso_strings(self):
        payload = to_primitive(self.engine.compute_ledger(
            self.filter, group_by=GroupBy.ACCOUNT))
        self.assertEqual(
            payload['groups'][0]['lines'][0]['source']['date'], '2026-01-05')

    def test_trial_balance_payload_shape(self):
        payload = to_primitive(self.engine.compute_trial_balance(
            LedgerFilter(date_to=date(2026, 1, 31), date_from=date(2026, 1, 1),
                         company_ids=(1,))))
        json.loads(json.dumps(payload))
        for key in ('rows', 'total_opening', 'total_movement', 'total_closing',
                    'is_balanced'):
            self.assertIn(key, payload)
        row = payload['rows'][0]
        for key in ('code', 'name', 'opening', 'movement', 'closing'):
            self.assertIn(key, row)

    def test_group_key_tuple_becomes_a_list(self):
        payload = to_primitive(self.engine.compute_ledger(
            self.filter, group_by=GroupBy.ACCOUNT))
        self.assertEqual(payload['groups'][0]['key'], [131])


if __name__ == '__main__':
    unittest.main()
