# -*- coding: utf-8 -*-
"""Foreign-currency ledger (S32-DN) and revaluation tests. No Odoo."""

import unittest
from datetime import date

from ..core.exceptions import ValidationException
from ..domain.ledger.calculators.revaluation import (
    PAYABLE, RECEIVABLE, RevaluationCalculator,
)
from ..domain.ledger.engine import LedgerEngine
from ..dto.filters import LedgerFilter
from ..dto.ledger import MoveLineDTO
from .fakes import FakeLedgerRepository
from .test_ledger_engine import ACCOUNTS, ACME, PARTNERS, USD


def _line(line_id, when, usd, vnd, account_id=131, currency_id=USD.id):
    return MoveLineDTO(
        id=line_id, date=when, account_id=account_id, journal_id=1,
        move_id=line_id, move_name='INV/%s' % line_id,
        debit=max(vnd, 0.0), credit=max(-vnd, 0.0), balance=vnd,
        partner_id=7, company_id=1, currency_id=currency_id,
        amount_currency=usd)


class TestCurrencyLedger(unittest.TestCase):

    lines = (
        _line(1, date(2026, 3, 10), 100.0, 2500000.0),     # before the period
        _line(2, date(2026, 4, 5), 200.0, 5100000.0),
        _line(3, date(2026, 4, 20), -50.0, -1300000.0),     # collected
        _line(4, date(2026, 4, 25), 0.0, 999.0, currency_id=1),  # in VND
    )

    def setUp(self):
        repo = FakeLedgerRepository(companies=(ACME,), accounts=ACCOUNTS,
                                    lines=self.lines, partners=PARTNERS)
        self.ledger = LedgerEngine(repo).compute_currency_ledger(LedgerFilter(
            date_from=date(2026, 4, 1), date_to=date(2026, 4, 30),
            company_ids=(1,), currency_id=USD.id))

    def test_one_group_per_partner_and_account_in_that_currency(self):
        self.assertEqual([g.group.key for g in self.ledger.groups], [(7, 131)])

    def test_currency_and_converted_balances(self):
        group = self.ledger.groups[0]
        self.assertEqual(group.opening_currency, 100.0)
        self.assertEqual((group.debit_currency, group.credit_currency),
                         (200.0, 50.0))
        self.assertEqual(group.closing_currency, 250.0)
        self.assertEqual(group.group.opening.balance, 2500000.0)
        self.assertEqual(group.group.closing.balance, 6300000.0)

    def test_lines_carry_rate_and_running_currency_balance(self):
        lines = self.ledger.groups[0].lines
        self.assertEqual([l.rate for l in lines], [25500.0, 26000.0])
        self.assertEqual([l.balance_currency for l in lines], [300.0, 250.0])

    def test_currency_is_required(self):
        repo = FakeLedgerRepository(companies=(ACME,), accounts=ACCOUNTS)
        with self.assertRaises(ValidationException):
            LedgerEngine(repo).compute_currency_ledger(LedgerFilter(
                date_to=date(2026, 4, 30), company_ids=(1,)))


class TestRevaluation(unittest.TestCase):

    rates = {USD.id: 26000.0}

    def test_difference_is_closing_value_less_book_value(self):
        result = RevaluationCalculator.differences(
            {(1122, None, USD.id): (1000.0, 25500000.0),
             (341, 9, USD.id): (-500.0, -12600000.0)}, self.rates, 1.0)
        self.assertEqual(result, {(1122, None, USD.id): 500000.0,
                                  (341, 9, USD.id): -400000.0})

    def test_advances_are_not_revalued(self):
        balances = {(131, 7, USD.id): (-100.0, -2500000.0),   # customer paid
                    (331, 8, USD.id): (100.0, 2500000.0),     # we paid ahead
                    (331, 9, USD.id): (-100.0, -2500000.0)}   # we owe
        result = RevaluationCalculator.differences(
            balances, self.rates, 1.0, {131: RECEIVABLE, 331: PAYABLE})
        self.assertEqual(result, {(331, 9, USD.id): -100000.0})

    def test_nothing_to_post_when_already_at_the_closing_rate(self):
        self.assertEqual(RevaluationCalculator.differences(
            {(1122, None, USD.id): (10.0, 260000.0)}, self.rates, 1.0), {})
