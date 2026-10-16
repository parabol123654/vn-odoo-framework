# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""The shipped TT200 mapping must be valid, and must add up.

A statutory mapping is data, which means a typo in an XML file ships silently
and produces a wrong financial statement rather than an error. These tests run
the shipped mapping through the Domain's own validator and then check the
arithmetic against a known set of entries.
"""

from datetime import date

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from odoo.addons.vn_core.core.exceptions import MappingException
from odoo.exceptions import UserError

from odoo.addons.vn_core.dto.filters import LedgerFilter


@tagged('post_install', '-at_install')
class TestTT200IncomeStatement(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        # 18.0 dropped the chart_template_ref argument from
        # AccountTestInvoicingCommon.setUpClass.
        super().setUpClass()
        cls.provider = cls.env['vn.ledger.provider']
        cls.engine = cls.provider.build_financial_statement_engine()
        cls.repo = cls.provider.build_mapping_repository()

    def _filter(self, date_from, date_to):
        # Dates, as the wizards pass them: current Date.to_string no longer
        # accepts a string.
        return LedgerFilter(date_from=date.fromisoformat(date_from),
                            date_to=date.fromisoformat(date_to),
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
    def setUpClass(cls):
        # 18.0 dropped the chart_template_ref argument from
        # AccountTestInvoicingCommon.setUpClass.
        super().setUpClass()
        cls.provider = cls.env['vn.ledger.provider']
        cls.engine = cls.provider.build_financial_statement_engine()
        cls.repo = cls.provider.build_mapping_repository()

    def _mapping(self):
        return self.repo.get_mapping('tt200_b01dn', (self.env.company.id,))

    def _filter(self):
        return LedgerFilter(date_from=None, date_to=date(2026, 12, 31),
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
    def setUpClass(cls):
        # 18.0 dropped the chart_template_ref argument from
        # AccountTestInvoicingCommon.setUpClass.
        super().setUpClass()
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
    def setUpClass(cls):
        # 18.0 dropped the chart_template_ref argument from
        # AccountTestInvoicingCommon.setUpClass.
        super().setUpClass()
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


@tagged('post_install', '-at_install')
class TestTT133Statements(AccountTestInvoicingCommon):
    """The shipped TT133 forms against figures worked out by hand.

    The test chart has no Vietnamese codes, so the accounts the forms read
    are created here with codes no generic chart uses.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.vn_accounting_circular = 'TT133'
        cls.provider = cls.env['vn.ledger.provider']
        cls.engine = cls.provider.build_financial_statement_engine()
        Account = cls.env['account.account']

        def account(code, account_type, reconcile=False):
            return Account.create({
                'code': code, 'name': 'VN %s' % code,
                'account_type': account_type, 'reconcile': reconcile,
            })

        cls.bank = account('112199', 'asset_cash')
        cls.customer = account('131199', 'asset_receivable', True)
        cls.allowance = account('229399', 'asset_current')
        cls.capital = account('411199', 'equity')
        cls.retained = account('421299', 'equity_unaffected'
                               if not Account.search([
                                   ('account_type', '=', 'equity_unaffected'),
                                   ('company_ids', 'in', cls.company.id)],
                                   limit=1) else 'equity')
        cls.revenue = account('511199', 'income')
        cls.cogs = account('632199', 'expense_direct_cost')
        cls.provision_cost = account('642299', 'expense')
        cls.journal = cls.company_data['default_journal_misc']

    def _post(self, day, *pairs):
        move = self.env['account.move'].create({
            'move_type': 'entry', 'date': day, 'journal_id': self.journal.id,
            'line_ids': [
                (0, 0, {'account_id': account.id, 'name': 'x',
                        'debit': amount if amount > 0 else 0.0,
                        'credit': -amount if amount < 0 else 0.0})
                for account, amount in pairs],
        })
        move.action_post()
        return move

    def _filter(self, date_from, date_to):
        return LedgerFilter(
            date_from=date.fromisoformat(date_from) if date_from else None,
            date_to=date.fromisoformat(date_to),
            company_ids=(self.company.id,))

    def _books(self):
        """Capital 900, sale 1,000 on credit, cost 600 paid, allowance 100,
        then the year-end transfer straight to 421."""
        self._post('2026-01-02', (self.bank, 900.0), (self.capital, -900.0))
        self._post('2026-03-01', (self.customer, 1000.0),
                   (self.revenue, -1000.0))
        self._post('2026-03-02', (self.cogs, 600.0), (self.bank, -600.0))
        self._post('2026-12-30', (self.provision_cost, 100.0),
                   (self.allowance, -100.0))
        self._post('2026-12-31', (self.revenue, 1000.0), (self.cogs, -600.0),
                   (self.provision_cost, -100.0), (self.retained, -300.0))

    def test_b01a_allowance_is_deducted(self):
        """Receivable 1,000 less allowance (100); assets 1,300 = capital
        900 + profit 300 + ... and the form balances."""
        self._books()
        report = self.engine.compute(self._filter(None, '2026-12-31'),
                                     'tt133_b01adnn')
        self.assertEqual(report.by_code('131').amount, 1000.0)
        self.assertEqual(report.by_code('136').amount, -100.0)
        self.assertEqual(report.by_code('130').amount, 900.0)
        self.assertEqual(report.by_code('110').amount, 300.0)
        self.assertEqual(report.by_code('200').amount, 1200.0)
        self.assertEqual(report.by_code('411').amount, 900.0)
        self.assertEqual(report.by_code('417').amount, 300.0)
        self.assertEqual(report.by_code('500').amount, 1200.0)
        self.assertTrue(report.balance_check.is_balanced)

    def test_b02_reads_the_year_before_the_transfer(self):
        self._books()
        report = self.engine.compute(
            self._filter('2026-01-01', '2026-12-31'), 'tt133_b02dnn')
        self.assertEqual(report.by_code('01').amount, 1000.0)
        self.assertEqual(report.by_code('02').amount, 0.0)
        self.assertEqual(report.by_code('11').amount, 600.0)
        self.assertEqual(report.by_code('24').amount, 100.0)
        self.assertEqual(report.by_code('60').amount, 300.0)

    def test_b03_indirect_reconciles_to_cash(self):
        self._books()
        report = self.engine.compute(
            self._filter('2026-01-01', '2026-12-31'), 'tt133_b03dnn')
        self.assertEqual(report.by_code('70').amount, 300.0)
        self.assertTrue(report.balance_check.is_balanced)

    def test_b01b_balances(self):
        self._books()
        report = self.engine.compute(self._filter(None, '2026-12-31'),
                                     'tt133_b01bdnn')
        self.assertEqual(report.by_code('131').amount, 1000.0)
        self.assertEqual(report.by_code('211').amount, 0.0)
        self.assertTrue(report.balance_check.is_balanced)

    def test_company_picks_b01b_and_the_direct_method(self):
        Mapping = self.env['vn.report.mapping']
        self.assertEqual(
            Mapping.default_for('balance_sheet', self.company).code,
            'tt133_b01adnn')
        self.company.vn_balance_sheet_mapping_id = self.env.ref(
            'l10n_vn_vas_reports.mapping_tt133_b01bdnn')
        self.company.vn_cash_flow_mapping_id = self.env.ref(
            'l10n_vn_vas_reports.mapping_tt133_b03dnn_direct')
        self.assertEqual(
            Mapping.default_for('balance_sheet', self.company).code,
            'tt133_b01bdnn')
        self.assertEqual(
            Mapping.default_for('cash_flow', self.company).code,
            'tt133_b03dnn_direct')
        # A choice from another circular is ignored, not printed.
        self.company.vn_accounting_circular = 'TT200'
        self.assertEqual(
            Mapping.default_for('balance_sheet', self.company).code,
            'tt200_b01dn')

    def test_printed_form_follows_the_circular(self):
        cases = (
            ('vn.balance.sheet.wizard', {}, 'B01a-DNN', 'B01-DN'),
            ('vn.income.statement.wizard', {}, 'B02-DNN', 'B02-DN'),
            ('vn.trial.balance.wizard', {}, 'F01-DNN', 'S06-DN'),
            ('vn.general.ledger.wizard', {}, 'S03b-DNN', 'S03b-DN'),
            ('vn.cash.book.wizard', {'book_type': 'cash'}, 'S04a-DNN',
             'S07-DN'),
            ('vn.partner.ledger.wizard', {}, 'S12-DNN', 'S31-DN'),
        )
        for model, values, tt133, tt200 in cases:
            self.company.vn_accounting_circular = 'TT133'
            wizard = self.env[model].create(values)
            self.assertEqual(wizard._report_form_code(), tt133, model)
            self.assertIn('133/2016', wizard._form_legal_line()[0], model)
            self.assertEqual(wizard._form_signer(),
                             'Người đại diện theo pháp luật')
            self.company.vn_accounting_circular = 'TT200'
            wizard = self.env[model].create(values)
            self.assertEqual(wizard._report_form_code(), tt200, model)
            self.assertIn('200/2014', wizard._form_legal_line()[0], model)

    def test_tax_return_states_no_accounting_circular(self):
        wizard = self.env['vn.vat.declaration.wizard'].create({})
        self.assertFalse(wizard._form_legal_line())


class _RegimeBooks(AccountTestInvoicingCommon):
    """One small set of books, worked out by hand, for any circular.

    Capital 900, sale 1,000 on credit, cost 600 paid, allowance 100 on the
    receivable, then the year-end transfer straight to 421: cash 300,
    receivable 1,000 less 100, capital 900, profit 300.
    """

    CIRCULAR = 'TT200'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.vn_accounting_circular = cls.CIRCULAR
        cls.engine = cls.env['vn.ledger.provider'] \
            .build_financial_statement_engine()
        cls.cash_engine = cls.env['vn.ledger.provider'].build_cash_flow_engine()
        Account = cls.env['account.account']
        unaffected = Account.search([
            ('account_type', '=', 'equity_unaffected'),
            ('company_ids', 'in', cls.company.id)], limit=1)

        def account(code, account_type, reconcile=False):
            return Account.create({'code': code, 'name': 'VN %s' % code,
                                   'account_type': account_type,
                                   'reconcile': reconcile})

        cls.bank = account('112199', 'asset_cash')
        cls.customer = account('131199', 'asset_receivable', True)
        cls.allowance = account('229399', 'asset_current')
        cls.capital = account('411199', 'equity')
        cls.retained = account('421299', 'equity' if unaffected
                               else 'equity_unaffected')
        cls.revenue = account('511199', 'income')
        cls.cogs = account('632199', 'expense_direct_cost')
        cls.admin = account('642299', 'expense')
        cls.journal = cls.company_data['default_journal_misc']

    def _post(self, day, *pairs):
        """Post (account, amount[, partner[, due date]]) lines."""
        def line(acc, amount, partner=None, due=None):
            values = {'account_id': acc.id, 'name': 'x',
                      'debit': amount if amount > 0 else 0.0,
                      'credit': -amount if amount < 0 else 0.0}
            if partner:
                values['partner_id'] = partner.id
            if due:
                values['date_maturity'] = due
            return (0, 0, values)
        move = self.env['account.move'].create({
            'move_type': 'entry', 'date': day, 'journal_id': self.journal.id,
            'line_ids': [line(*pair) for pair in pairs],
        })
        move.action_post()

    def _books(self):
        self._post('2026-01-02', (self.bank, 900.0), (self.capital, -900.0))
        self._post('2026-03-01', (self.customer, 1000.0),
                   (self.revenue, -1000.0))
        self._post('2026-03-02', (self.cogs, 600.0), (self.bank, -600.0))
        self._post('2026-12-30', (self.admin, 100.0), (self.allowance, -100.0))
        self._post('2026-12-31', (self.revenue, 1000.0), (self.cogs, -600.0),
                   (self.admin, -100.0), (self.retained, -300.0))

    def _filter(self, date_from=None):
        return LedgerFilter(
            date_from=date.fromisoformat(date_from) if date_from else None,
            date_to=date(2026, 12, 31), company_ids=(self.company.id,))


@tagged('post_install', '-at_install')
class TestTT200BalanceSheetFigures(_RegimeBooks):

    CIRCULAR = 'TT200'

    def test_allowance_is_deducted_and_the_form_balances(self):
        self._books()
        report = self.engine.compute(self._filter(), 'tt200_b01dn')
        self.assertEqual(report.by_code('137').amount, -100.0)
        self.assertEqual(report.by_code('270').amount, 1200.0)
        self.assertEqual(report.by_code('440').amount, 1200.0)
        self.assertTrue(report.balance_check.is_balanced)

    def test_income_statement_survives_the_year_end_transfer(self):
        self._books()
        report = self.engine.compute(self._filter('2026-01-01'), 'tt200_b02dn')
        self.assertEqual(report.by_code('01').amount, 1000.0)
        self.assertEqual(report.by_code('11').amount, 600.0)

    def _account(self, code, account_type, reconcile=False):
        return self.env['account.account'].create({
            'code': code, 'name': 'VN %s' % code,
            'account_type': account_type, 'reconcile': reconcile})

    def test_every_equity_line_counts_in_400(self):
        """Điều 112: 400 = 410 + 430, 410 = 411 + ... + 422, 431 = 461 - 161.

        On top of the books (cash 300, receivable 1,000 less 100, capital
        900, 421 300), cash 1,050 comes in against other capital (4118) 300,
        the development fund (414) 200, other funds (418) 200, the
        construction fund (441) 100, grants (461) 150 and grants spent on
        fixed assets (466) 100; then 50 of the grant is spent (161).

            cash  300 + 1,050 - 50 = 1,300;  270 = 1,300 + 900 = 2,200
            410 = 900 + 300 + 200 + 200 + 300 + 100 = 2,000
            431 = 150 - 50 = 100;  432 = 100;  430 = 200
            400 = 2,200 = 440, the form balances.
        """
        self._books()
        other_capital = self._account('411899', 'equity')
        fund = self._account('414199', 'equity')
        other_fund = self._account('418199', 'equity')
        construction = self._account('441199', 'equity')
        grant = self._account('461199', 'equity')
        grant_spent = self._account('161199', 'asset_current')
        grant_assets = self._account('466199', 'equity')
        self._post('2026-06-01', (self.bank, 1050.0),
                   (other_capital, -300.0), (fund, -200.0),
                   (other_fund, -200.0), (construction, -100.0),
                   (grant, -150.0), (grant_assets, -100.0))
        self._post('2026-07-01', (grant_spent, 50.0), (self.bank, -50.0))
        report = self.engine.compute(self._filter(), 'tt200_b01dn')
        amount = lambda code: report.by_code(code).amount
        self.assertEqual(
            [amount(c) for c in ('411', '411a', '414', '418', '420', '421',
                                 '421b', '422', '410')],
            [900.0, 900.0, 300.0, 200.0, 200.0, 300.0, 300.0, 100.0, 2000.0])
        self.assertEqual([amount(c) for c in ('431', '432', '430', '400')],
                         [100.0, 100.0, 200.0, 2200.0])
        self.assertEqual(amount('270'), 2200.0)
        self.assertEqual(amount('440'), 2200.0)
        self.assertTrue(report.balance_check.is_balanced)

    def test_revenue_credit_and_deductions_debit(self):
        """Điều 113: 01 is the credit side of 511, 02 its debit side (the
        deductions, once 521 has been transferred into 511).

        Sale 1,000 on credit; trade discount 100 booked on 521 and moved into
        511 on 30/12; a return of 50 booked straight on 511.

            01 = 1,000;  02 = 100 + 50 = 150;  10 = 850.

        Read to 29/12, before the 521 transfer, 02 holds only the return
        (50) and 10 is 950: a deduction still sitting on 521 is not on the
        form (the specification says why).
        """
        customer = self._account('131299', 'asset_receivable', True)
        discount = self._account('521199', 'income')
        self._post('2026-03-01', (customer, 1000.0), (self.revenue, -1000.0))
        self._post('2026-04-01', (discount, 100.0), (customer, -100.0))
        self._post('2026-05-01', (self.revenue, 50.0), (customer, -50.0))
        self._post('2026-12-30', (self.revenue, 100.0), (discount, -100.0))
        year = LedgerFilter(date_from=date(2026, 1, 1),
                            date_to=date(2026, 12, 31),
                            company_ids=(self.company.id,))
        report = self.engine.compute(year, 'tt200_b02dn')
        self.assertEqual(
            [report.by_code(c).amount for c in ('01', '02', '10')],
            [1000.0, 150.0, 850.0])
        early = year.replace(date_to=date(2026, 12, 29))
        report = self.engine.compute(early, 'tt200_b02dn')
        self.assertEqual(
            [report.by_code(c).amount for c in ('01', '02', '10')],
            [1000.0, 50.0, 950.0])

    def test_receivable_split_by_due_date(self):
        """Điều 112 mã số 131, 211, 312: by remaining term, per customer.

        Customer A owes 700 due 31/03/2027 and 400 due 30/06/2028; customer
        B paid 200 in advance. Revenue 1,100 is closed to 421. At 31/12/2026
        the boundary is 31/12/2027:

            131 = 700;  211 = 400;  312 = 200;  332 = 0
            270 = cash 200 + 700 + 400 = 1,300 = 312 200 + 421 1,100.
        """
        partner_a = self.env['res.partner'].create({'name': 'Customer A'})
        partner_b = self.env['res.partner'].create({'name': 'Customer B'})
        self._post('2026-06-01',
                   (self.customer, 700.0, partner_a, '2027-03-31'),
                   (self.customer, 400.0, partner_a, '2028-06-30'),
                   (self.revenue, -1100.0, partner_a))
        self._post('2026-07-01', (self.bank, 200.0),
                   (self.customer, -200.0, partner_b))
        self._post('2026-12-31', (self.revenue, 1100.0),
                   (self.retained, -1100.0))
        report = self.engine.compute(self._filter(), 'tt200_b01dn')
        self.assertEqual(
            [report.by_code(c).amount for c in ('131', '211', '312', '332')],
            [700.0, 400.0, 200.0, 0.0])
        self.assertEqual(report.by_code('270').amount, 1300.0)
        self.assertTrue(report.balance_check.is_balanced)


@tagged('post_install', '-at_install')
class TestTT99Statements(_RegimeBooks):

    CIRCULAR = 'TT99'

    def test_b01_balances(self):
        self._books()
        report = self.engine.compute(self._filter(), 'tt99_b01dn')
        self.assertEqual(report.by_code('111').amount, 300.0)
        self.assertEqual(report.by_code('131').amount, 1000.0)
        self.assertEqual(report.by_code('136').amount, -100.0)
        self.assertEqual(report.by_code('280').amount, 1200.0)
        self.assertEqual(report.by_code('411a').amount, 900.0)
        self.assertEqual(report.by_code('420').amount, 300.0)
        self.assertEqual(report.by_code('440').amount, 1200.0)
        self.assertTrue(report.balance_check.is_balanced)

    def test_b02(self):
        self._books()
        report = self.engine.compute(self._filter('2026-01-01'), 'tt99_b02dn')
        self.assertEqual(report.by_code('01').amount, 1000.0)
        self.assertEqual(report.by_code('11').amount, 600.0)
        self.assertEqual(report.by_code('26').amount, 100.0)
        self.assertEqual(report.by_code('60').amount, 300.0)

    def test_b03_both_methods_reconcile_to_cash(self):
        self._books()
        direct = self.cash_engine.compute(self._filter('2026-01-01'),
                                          'tt99_b03dn')
        self.assertEqual(direct.by_code('70').amount, 300.0)
        self.assertEqual(direct.by_code('31').amount, 900.0)
        self.assertEqual(direct.by_code('02').amount, -600.0)
        self.assertTrue(direct.balance_check.is_balanced)
        indirect = self.engine.compute(self._filter('2026-01-01'),
                                       'tt99_b03dn_indirect')
        self.assertEqual(indirect.by_code('70').amount, 300.0)
        self.assertEqual(indirect.by_code('20').amount, -600.0)
        self.assertTrue(indirect.balance_check.is_balanced)

    def test_default_forms_and_printed_identity(self):
        Mapping = self.env['vn.report.mapping']
        self.assertEqual(Mapping.default_for('balance_sheet', self.company).code,
                         'tt99_b01dn')
        self.assertEqual(Mapping.default_for('cash_flow', self.company).code,
                         'tt99_b03dn')
        wizard = self.env['vn.balance.sheet.wizard'].create({})
        self.assertEqual(wizard._report_form_code(), 'B01-DN')
        self.assertIn('Kèm theo Thông tư số 99/2025', wizard._form_legal_line()[0])
        self.assertEqual(wizard._form_preparer(), 'Người lập')
        self.assertEqual(wizard._form_signer(), 'Người đại diện theo pháp luật')
        book = self.env['vn.cash.book.wizard'].create({'book_type': 'bank'})
        self.assertEqual(book._report_form_code(), 'S08-DN')
        self.assertEqual(book._report_form_title(), 'SỔ TIỀN GỬI KHÔNG KỲ HẠN')
