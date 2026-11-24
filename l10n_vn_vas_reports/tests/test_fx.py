# -*- coding: utf-8 -*-
# Target: Odoo 20.0 Community Edition
"""Foreign-currency ledger (S32-DN) and period-end revaluation."""

from datetime import date

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestFx(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # 1 EUR = 2 company units in January, 4 from mid-June.
        cls.eur = cls.setup_other_currency(
            'EUR', rates=[('2026-01-01', 0.5), ('2026-06-15', 0.25)])
        cls.invoice = cls.init_invoice(
            'out_invoice', amounts=[100.0], currency=cls.eur,
            invoice_date='2026-01-15', post=True)
        cls.receivable = cls.company_data['default_account_receivable']
        cls.account_413 = cls.env['account.account'].create({
            'code': '413100', 'name': 'Chênh lệch tỷ giá',
            'account_type': 'liability_current'})

    def _receivable_balance(self, at):
        lines = self.env['account.move.line'].search([
            ('account_id', '=', self.receivable.id),
            ('parent_state', '=', 'posted'), ('date', '<=', at)])
        return sum(lines.mapped('balance'))

    def test_currency_ledger_shows_both_amounts(self):
        wizard = self.env['vn.currency.ledger.wizard'].create({
            'date_from': '2026-01-01', 'date_to': '2026-03-31',
            'foreign_currency_id': self.eur.id})
        group = wizard._build_report().groups[0]
        self.assertEqual(group.closing_currency, 100.0)
        self.assertEqual(group.group.closing.balance, 200.0)
        self.assertEqual(group.lines[0].rate, 2.0)
        self.assertIn('S32-DN', wizard.get_report_html())

    def test_revaluation_books_the_gain_and_reverses_next_day(self):
        wizard = self.env['vn.fx.revaluation.wizard'].create({
            'date': '2026-06-30', 'account_ids': [(6, 0, self.receivable.ids)],
            'revaluation_account_id': self.account_413.id})
        wizard.action_load_rates()
        self.assertEqual(wizard.rate_ids.rate, 4.0)

        move = self.env['account.move'].browse(wizard.action_post()['res_id'])
        gain = self.env.company.income_currency_exchange_account_id
        self.assertEqual(move.state, 'posted')
        self.assertEqual(sum(move.line_ids.filtered(
            lambda l: l.account_id == gain).mapped('balance')), -200.0)
        self.assertEqual(sum(move.line_ids.filtered(
            lambda l: l.account_id == self.account_413).mapped('balance')), 0.0)

        self.assertEqual(self._receivable_balance(date(2026, 6, 30)), 400.0)
        self.assertEqual(self._receivable_balance(date(2026, 7, 1)), 200.0)
        reversal = self.env['account.move'].search(
            [('reversed_entry_id', '=', move.id)])
        self.assertEqual(reversal.date, date(2026, 7, 1))
