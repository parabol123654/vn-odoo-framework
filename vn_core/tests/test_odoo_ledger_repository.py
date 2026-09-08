# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""Repository integration tests (Part 6 §21).

The Domain is already covered without a database; what needs a real Odoo here is
narrower: that the SQL executes, that it maps onto the DTOs the interface
promises, and that record rules are enforced rather than bypassed.
"""

from datetime import date

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from ..core.enums import GroupBy, TargetMove
from ..dto.filters import LedgerFilter
from ..dto.ledger import MoveLineDTO
from ..services.general_ledger_service import (
    GeneralLedgerService, TrialBalanceService,
)


@tagged('post_install', '-at_install')
class TestOdooLedgerRepository(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.provider = cls.env['vn.ledger.provider']
        cls.repo = cls.provider.build_ledger_repository()
        cls.journal = cls.company_data['default_journal_misc']
        cls.receivable = cls.company_data['default_account_receivable']
        cls.revenue = cls.company_data['default_account_revenue']

        cls.entry_2025 = cls._entry('2025-06-15', 1000.0)
        cls.entry_jan = cls._entry('2026-01-20', 300.0)
        cls.entry_apr = cls._entry('2026-04-10', 500.0)

    @classmethod
    def _entry(cls, when, amount, post=True):
        move = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': when,
            'journal_id': cls.journal.id,
            'line_ids': [
                (0, 0, {'account_id': cls.receivable.id,
                                'debit': amount, 'credit': 0.0,
                                'name': 'Bán hàng'}),
                (0, 0, {'account_id': cls.revenue.id,
                                'debit': 0.0, 'credit': amount,
                                'name': 'Bán hàng'}),
            ],
        })
        if post:
            move.action_post()
        return move

    def _filter(self, date_from, date_to, **kwargs):
        return LedgerFilter(date_to=date_to, date_from=date_from,
                            company_ids=(self.env.company.id,), **kwargs)

    # ------------------------------------------------------------------
    # Contract
    # ------------------------------------------------------------------
    def test_accounts_carry_the_initial_balance_flag(self):
        """The flag the fiscal-year rule depends on must survive the mapping."""
        accounts = {a.id: a for a in self.repo.get_accounts(
            self._filter(None, date(2026, 12, 31)))}
        self.assertTrue(accounts[self.receivable.id].include_initial_balance)
        self.assertFalse(accounts[self.revenue.id].include_initial_balance)

    def test_company_dto_carries_currency_and_fiscal_year(self):
        company = self.repo.get_companies((self.env.company.id,))[0]
        self.assertEqual(company.currency.id, self.env.company.currency_id.id)
        self.assertEqual(company.fiscalyear_last_month,
                         int(self.env.company.fiscalyear_last_month))

    def test_move_lines_are_dtos_in_chronological_order(self):
        lines = self.repo.get_move_lines(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)))
        self.assertTrue(all(isinstance(line, MoveLineDTO) for line in lines))
        self.assertEqual([line.date for line in lines],
                         [date(2026, 1, 20), date(2026, 1, 20),
                          date(2026, 4, 10), date(2026, 4, 10)])
        self.assertTrue(all(line.move_name for line in lines))

    def test_aggregate_respects_the_supplied_window(self):
        """The repository must not apply any fiscal-year rule of its own."""
        totals = self.repo.aggregate_balances(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)),
            GroupBy.ACCOUNT.fields, None, date(2025, 12, 31))
        self.assertEqual(totals[(self.receivable.id,)].debit, 1000.0)
        # Revenue is included too: deciding to reset it is the Engine's job.
        self.assertEqual(totals[(self.revenue.id,)].credit, 1000.0)

    def test_aggregate_grouped_by_partner(self):
        totals = self.repo.aggregate_balances(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)),
            GroupBy.PARTNER.fields, date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(sum(b.debit for b in totals.values()), 800.0)

    def test_move_account_sums_report_raw_totals(self):
        sums = self.repo.get_move_account_sums((self.entry_jan.id,))
        by_account = {row.account_id: row for row in sums}
        self.assertEqual(by_account[self.receivable.id].debit, 300.0)
        self.assertEqual(by_account[self.revenue.id].credit, 300.0)

    def test_draft_entries_only_appear_for_target_move_all(self):
        self._entry('2026-02-01', 700.0, post=False)
        posted = self.repo.aggregate_balances(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)),
            GroupBy.ACCOUNT.fields, date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(posted[(self.receivable.id,)].debit, 800.0)

        with_draft = self.repo.aggregate_balances(
            self._filter(date(2026, 1, 1), date(2026, 12, 31),
                         target_move=TargetMove.ALL),
            GroupBy.ACCOUNT.fields, date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(with_draft[(self.receivable.id,)].debit, 1500.0)

    def test_ungroupable_column_is_rejected(self):
        from ..core.exceptions import RepositoryException
        with self.assertRaises(RepositoryException):
            self.repo.aggregate_balances(
                self._filter(None, date(2026, 12, 31)),
                ('id); DROP TABLE account_move_line; --',),
                None, date(2026, 12, 31))

    # ------------------------------------------------------------------
    # End to end
    # ------------------------------------------------------------------
    def test_trial_balance_through_the_service(self):
        result = TrialBalanceService(self.env).generate(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)))
        self.assertTrue(result.success)

        rows = {row.account_id: row for row in result.data.rows}
        # Balance-sheet account carries 2025 forward...
        self.assertEqual(rows[self.receivable.id].opening.debit_balance, 1000.0)
        # ...while the P&L account resets at the fiscal year start.
        self.assertEqual(rows[self.revenue.id].opening.balance, 0.0)

    def test_general_ledger_running_balance_and_counterpart(self):
        result = GeneralLedgerService(self.env).generate(
            self._filter(date(2026, 1, 1), date(2026, 12, 31),
                         account_ids=(self.receivable.id,)))
        self.assertTrue(result.success)

        group = result.data.groups[0]
        self.assertEqual(group.opening.debit_balance, 1000.0)
        self.assertEqual([line.running_balance for line in group.lines],
                         [1300.0, 1800.0])
        self.assertEqual(group.lines[0].counterpart_label, self.revenue.code)

    def test_service_reports_failure_instead_of_raising(self):
        result = TrialBalanceService(self.env).generate(
            self._filter(date(2026, 12, 31), date(2026, 1, 1)))
        self.assertFalse(result.success)
        self.assertTrue(result.errors)

    # ------------------------------------------------------------------
    # Isolation
    # ------------------------------------------------------------------
    def test_other_company_data_is_not_returned(self):
        """Raw SQL still goes through _apply_ir_rules, so isolation holds."""
        other = self.setup_company_data('VAS Second Company')
        other_move = self.env['account.move'].with_company(
            other['company']).create({
                'move_type': 'entry',
                'date': '2026-03-01',
                'journal_id': other['default_journal_misc'].id,
                'line_ids': [
                    (0, 0, {
                        'account_id': other['default_account_receivable'].id,
                        'debit': 999.0, 'credit': 0.0, 'name': 'Other'}),
                    (0, 0, {
                        'account_id': other['default_account_revenue'].id,
                        'debit': 0.0, 'credit': 999.0, 'name': 'Other'}),
                ],
            })
        other_move.action_post()

        lines = self.repo.get_move_lines(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)))
        self.assertNotIn(other['company'].id,
                         {line.company_id for line in lines})
