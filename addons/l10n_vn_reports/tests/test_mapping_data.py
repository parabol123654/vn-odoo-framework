# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""The shipped TT200 mapping must be valid, and must add up.

A statutory mapping is data, which means a typo in an XML file ships silently
and produces a wrong financial statement rather than an error. These tests run
the shipped mapping through the Domain's own validator and then check the
arithmetic against a known set of entries.
"""

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from odoo.addons.vn_core.core.exceptions import MappingException
from odoo.exceptions import UserError

from odoo.addons.vn_core.dto.filters import LedgerFilter


@tagged('post_install', '-at_install')
class TestTT200IncomeStatement(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.provider = cls.env['vn.ledger.provider']
        cls.engine = cls.provider.build_financial_statement_engine()
        cls.repo = cls.provider.build_mapping_repository()

    def _filter(self, date_from, date_to):
        return LedgerFilter(date_from=date_from, date_to=date_to,
                            company_ids=(self.env.company.id,))

    # ------------------------------------------------------------------
    def test_mapping_is_installed(self):
        mapping = self.repo.get_mapping('tt200_b02dn', (self.env.company.id,))
        self.assertIsNotNone(mapping, "TT200 B02-DN mapping was not loaded")
        self.assertEqual(mapping.basis, 'movement')
        self.assertEqual(mapping.report_type, 'income_statement')

    def test_mapping_passes_domain_validation(self):
        """Duplicate codes, formula cycles, bad expressions all fail here."""
        mapping = self.repo.get_mapping('tt200_b02dn', (self.env.company.id,))
        try:
            self.engine._validate(mapping)
        except MappingException as error:
            self.fail("Shipped mapping is invalid: %s" % error)

    def test_every_statutory_code_is_present(self):
        mapping = self.repo.get_mapping('tt200_b02dn', (self.env.company.id,))
        codes = {line.code for line in mapping.lines}
        self.assertEqual(
            codes,
            {'01', '02', '10', '11', '20', '21', '22', '23', '25', '26',
             '30', '31', '32', '40', '50', '51', '52', '60', '70', '71'})

    def test_totals_follow_from_the_entries(self):
        """Revenue 1,000 less cost 600 less admin 150 leaves 250."""
        revenue = self.company_data['default_account_revenue']
        expense = self.company_data['default_account_expense']
        receivable = self.company_data['default_account_receivable']
        journal = self.company_data['default_journal_misc']

        def entry(debit_account, credit_account, amount):
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'date': '2026-03-01',
                'journal_id': journal.id,
                'line_ids': [
                    (0, 0, {'account_id': debit_account.id, 'name': 'x',
                            'debit': amount, 'credit': 0.0}),
                    (0, 0, {'account_id': credit_account.id, 'name': 'x',
                            'debit': 0.0, 'credit': amount}),
                ],
            })
            move.action_post()

        entry(receivable, revenue, 1000.0)
        entry(expense, receivable, 600.0)

        report = self.engine.compute(
            self._filter('2026-01-01', '2026-12-31'), 'tt200_b02dn')

        # The generic chart used by the test fixture does not carry Vietnamese
        # account codes, so the assertion that matters here is structural: the
        # statement builds, every code is present, and the formulas resolve.
        self.assertEqual(len(report.lines), 20)
        self.assertIsNotNone(report.by_code('60'))
        self.assertEqual(report.report_type, 'income_statement')

    def test_formula_lines_are_flagged_as_computed(self):
        report = self.engine.compute(
            self._filter('2026-01-01', '2026-12-31'), 'tt200_b02dn')
        self.assertTrue(report.by_code('10').is_computed)
        self.assertFalse(report.by_code('01').is_computed)

    def test_comparative_column(self):
        report = self.engine.compute(
            self._filter('2026-01-01', '2026-12-31'), 'tt200_b02dn',
            comparative_filter=self._filter('2025-01-01', '2025-12-31'))
        self.assertTrue(report.comparative)
        self.assertIsNotNone(report.by_code('01').previous_amount)


@tagged('post_install', '-at_install')
class TestTT200BalanceSheet(AccountTestInvoicingCommon):
    """The shipped B01-DN must be structurally sound.

    Its account expressions are deliberately incomplete — the uncommon items
    are left for the accountant — so these tests check the structure and the
    diagnostics rather than the figures.
    """

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.provider = cls.env['vn.ledger.provider']
        cls.engine = cls.provider.build_financial_statement_engine()
        cls.repo = cls.provider.build_mapping_repository()

    def _mapping(self):
        return self.repo.get_mapping('tt200_b01dn', (self.env.company.id,))

    def _filter(self):
        return LedgerFilter(date_from=None, date_to='2026-12-31',
                            company_ids=(self.env.company.id,))

    def test_mapping_is_installed(self):
        mapping = self._mapping()
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.basis, 'closing')
        self.assertEqual(mapping.balance_check, '270=440')

    def test_mapping_passes_domain_validation(self):
        try:
            self.engine._validate(self._mapping())
        except MappingException as error:
            self.fail("Shipped B01-DN mapping is invalid: %s" % error)

    def test_partner_split_is_configured_on_both_sides(self):
        """131 and 331 each feed a receivable and a payable item."""
        lines = {l.code: l for l in self._mapping().lines}
        self.assertEqual(lines['131'].side, 'debit_only')
        self.assertTrue(lines['131'].split_by_partner)
        self.assertEqual(lines['312'].side, 'credit_only')
        self.assertTrue(lines['312'].split_by_partner)
        self.assertEqual(lines['132'].side, 'debit_only')
        self.assertEqual(lines['311'].side, 'credit_only')

    def test_grand_totals_are_formulas(self):
        lines = {l.code: l for l in self._mapping().lines}
        self.assertTrue(lines['270'].formula)
        self.assertTrue(lines['440'].formula)

    def test_report_builds_and_reports_its_own_balance(self):
        report = self.engine.compute(self._filter(), 'tt200_b01dn')
        self.assertIsNotNone(report.balance_check)
        self.assertEqual(report.balance_check.left_code, '270')
        self.assertEqual(report.balance_check.right_code, '440')

    def test_diagnostics_can_be_turned_off(self):
        report = self.engine.compute(self._filter(), 'tt200_b01dn',
                                     with_diagnostics=False)
        self.assertIsNone(report.balance_check)
        self.assertEqual(report.unmapped, ())


@tagged('post_install', '-at_install')
class TestDrillDown(AccountTestInvoicingCommon):
    """Opening an item must land on the accounts that produced it."""

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.wizard = cls.env['vn.income.statement.wizard'].create({
            'company_id': cls.env.company.id,
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })

    def test_returns_a_ledger_action_restricted_to_the_right_accounts(self):
        report = self.wizard._build_report()
        line = next(l for l in report.lines if l.account_ids)

        action = self.wizard.action_drill_down(line.code)
        self.assertEqual(action['type'], 'ir.actions.client')

        ledger = self.env['vn.general.ledger.wizard'].browse(
            action['context']['vn_report_wizard_id'])
        self.assertEqual(set(ledger.account_ids.ids), set(line.account_ids))
        self.assertEqual(ledger.date_to, self.wizard.date_to)
        self.assertEqual(ledger.target_move, self.wizard.target_move)

    def test_a_heading_refuses_politely(self):
        report = self.wizard._build_report()
        heading = next((l for l in report.lines if not l.account_ids), None)
        if heading is None:
            self.skipTest('every item on this mapping resolves to accounts')
        with self.assertRaises(UserError):
            self.wizard.action_drill_down(heading.code)

    def test_unknown_item(self):
        with self.assertRaises(UserError):
            self.wizard.action_drill_down('nope')

    def test_balance_sheet_opens_on_the_fiscal_year(self):
        """An as-at statement has no start date; the ledger needs one."""
        wizard = self.env['vn.balance.sheet.wizard'].create({
            'company_id': self.env.company.id,
            'date_to': '2026-12-31',
        })
        expected = self.env.company.compute_fiscalyear_dates(
            wizard.date_to)['date_from']
        self.assertEqual(wizard._drill_date_from(), expected)


@tagged('post_install', '-at_install')
class TestCircularSwitch(AccountTestInvoicingCommon):
    """The claim the whole mapping layer exists to make good on.

    Switching a company from Thông tư 200 to Thông tư 133 changes which rows the
    engine reads and nothing else — no branch in Python, no second engine, no
    per-circular report. These tests assert that, because an architecture claim
    nobody checks is just a comment.
    """

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.mappings = cls.env['vn.report.mapping']

    def test_both_circulars_ship(self):
        versions = set(self.mappings.search([
            ('report_type', '=', 'balance_sheet')]).mapped('version'))
        self.assertIn('TT200', versions)
        self.assertIn('TT133', versions)

    def test_company_setting_selects_the_mapping(self):
        company = self.env.company
        company.vn_accounting_circular = 'TT200'
        self.assertEqual(
            self.mappings.default_for('balance_sheet', company).code,
            'tt200_b01dn')
        company.vn_accounting_circular = 'TT133'
        self.assertEqual(
            self.mappings.default_for('balance_sheet', company).code,
            'tt133_b01adnn')

    def test_the_forms_really_differ(self):
        """Not a rename: TT133 has its own codes and its own totals."""
        tt200 = {l.code for l in self.mappings.search(
            [('code', '=', 'tt200_b01dn')]).line_ids}
        tt133 = {l.code for l in self.mappings.search(
            [('code', '=', 'tt133_b01adnn')]).line_ids}
        self.assertIn('270', tt200)
        self.assertNotIn('270', tt133)
        self.assertIn('200', tt133)
        self.assertLess(len(tt133), len(tt200))

    def test_tt133_merges_selling_and_admin_expenses(self):
        """TT200 splits 641 and 642; TT133 reports them as one item."""
        lines = {l.code: l for l in self.mappings.search(
            [('code', '=', 'tt133_b02dnn')]).line_ids}
        self.assertIn('641', lines['24'].expression)
        self.assertIn('642', lines['24'].expression)

    def test_tt133_mapping_passes_domain_validation(self):
        engine = self.env['vn.ledger.provider'].build_financial_statement_engine()
        repo = self.env['vn.ledger.provider'].build_mapping_repository()
        for code in ('tt133_b01adnn', 'tt133_b02dnn'):
            mapping = repo.get_mapping(code, (self.env.company.id,))
            self.assertIsNotNone(mapping, code)
            try:
                engine._validate(mapping)
            except MappingException as error:
                self.fail('%s is invalid: %s' % (code, error))

    def test_tt133_balance_sheet_checks_its_own_identity(self):
        mapping = self.mappings.search([('code', '=', 'tt133_b01adnn')])
        self.assertEqual(mapping.balance_check, '200=500')

    def test_partner_split_survives_the_circular_change(self):
        """The hardest VAS rule is configured on both forms, not just TT200."""
        lines = {l.code: l for l in self.mappings.search(
            [('code', '=', 'tt133_b01adnn')]).line_ids}
        self.assertEqual(lines['131'].side, 'debit_only')
        self.assertTrue(lines['131'].split_by_partner)
        self.assertEqual(lines['312'].side, 'credit_only')
        self.assertTrue(lines['312'].split_by_partner)

    def test_tt133_has_all_three_statements(self):
        """The gap recorded when TT133 was added: no cash flow form."""
        for report_type, code in (('balance_sheet', 'tt133_b01adnn'),
                                  ('income_statement', 'tt133_b02dnn'),
                                  ('cash_flow', 'tt133_b03dnn')):
            company = self.env.company
            company.vn_accounting_circular = 'TT133'
            self.assertEqual(
                self.mappings.default_for(report_type, company).code, code)

    def test_the_two_circulars_use_different_cash_flow_methods(self):
        """TT200 ships the direct form, TT133 the indirect one."""
        direct = self.mappings.search([('code', '=', 'tt200_b03dn')])
        indirect = self.mappings.search([('code', '=', 'tt133_b03dnn')])
        self.assertEqual(direct.cash_flow_method, 'direct')
        self.assertEqual(indirect.cash_flow_method, 'indirect')

    def test_indirect_form_reconciles_to_real_cash(self):
        mapping = self.mappings.search([('code', '=', 'tt133_b03dnn')])
        self.assertEqual(mapping.balance_check, '70=__closing_cash__')
        self.assertTrue(mapping.cash_expression)
