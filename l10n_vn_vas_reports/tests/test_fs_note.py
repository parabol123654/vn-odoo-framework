# -*- coding: utf-8 -*-
# Target: Odoo 16.0 Community Edition
"""Notes to the financial statements (B09-DNN) against hand-worked figures.

The books, two calendar years::

    2025  capital 2,000 into the bank; buy an asset for 1,200;
          depreciation 200; year-end transfer of the loss (200) to 421.
    2026  sale on credit 1,000 + VAT 100; VAT paid 60; asset bought for 300;
          depreciation 250; year-end transfer of the profit (750) to 421.

    End of 2025: bank 800, cost 1,200, depreciation 200, capital 2,000,
                 421 debit 200.
    End of 2026: bank 440, customer 1,100, cost 1,500, depreciation 450,
                 VAT payable 40, capital 2,000, 421 credit 550.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestFsNoteTT133(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.company = cls.env.company
        cls.company.vn_accounting_circular = 'TT133'
        Account = cls.env['account.account']

        def account(code, account_type, reconcile=False):
            return Account.create({
                'code': code, 'name': 'VN %s' % code,
                'account_type': account_type, 'reconcile': reconcile,
            })

        cls.bank = account('112199', 'asset_cash')
        cls.customer = account('131199', 'asset_receivable', True)
        cls.cost = account('211199', 'asset_fixed')
        cls.depreciation = account('214199', 'asset_fixed')
        cls.vat = account('333119', 'liability_current')
        cls.capital = account('411199', 'equity')
        cls.retained = account('421299', 'equity_unaffected'
                               if not Account.search([
                                   ('account_type', '=', 'equity_unaffected'),
                                   ('company_id', '=', cls.company.id)],
                                   limit=1) else 'equity')
        cls.revenue = account('511199', 'income')
        cls.expense = account('642299', 'expense')
        cls.journal = cls.company_data['default_journal_misc']
        cls.template = cls.env.ref('l10n_vn_vas_reports.fs_note_tt133_b09dnn')

    # -- helpers -------------------------------------------------------
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

    def _books(self):
        self._post('2025-01-05', (self.bank, 2000.0), (self.capital, -2000.0))
        self._post('2025-02-01', (self.cost, 1200.0), (self.bank, -1200.0))
        self._post('2025-12-31', (self.expense, 200.0),
                   (self.depreciation, -200.0))
        self._post('2025-12-31', (self.expense, -200.0),
                   (self.retained, 200.0))
        self._post('2026-03-01', (self.customer, 1100.0),
                   (self.revenue, -1000.0), (self.vat, -100.0))
        self._post('2026-04-01', (self.vat, 60.0), (self.bank, -60.0))
        self._post('2026-06-01', (self.cost, 300.0), (self.bank, -300.0))
        self._post('2026-12-31', (self.expense, 250.0),
                   (self.depreciation, -250.0))
        self._post('2026-12-31', (self.revenue, 1000.0),
                   (self.expense, -250.0), (self.retained, -750.0))

    def _note(self, year):
        return self.env['vn.fs.note'].create({
            'company_id': self.company.id,
            'template_id': self.template.id,
            'date_from': '%d-01-01' % year,
            'date_to': '%d-12-31' % year,
        })

    @staticmethod
    def _row(note, reference, code):
        row = note.row_ids.filtered(
            lambda r: r.item_id.reference == reference and r.code == code)
        row.ensure_one()
        return row

    def _figures(self, note, reference, code):
        row = self._row(note, reference, code)
        return (row.comparative, row.increase, row.decrease, row.current)

    # -- the shipped template ------------------------------------------
    def test_template_has_the_forms_tables(self):
        """B09-DNN has 22 numeric tables: V.1–V.13 and VI.1–VI.9."""
        tables = self.template.item_ids.filtered(lambda i: i.kind == 'table')
        self.assertEqual(len(tables), 22)
        self.assertEqual(
            sorted(tables.mapped('reference')),
            sorted(['V.%d' % n for n in range(1, 14)]
                   + ['VI.%d' % n for n in range(1, 10)]))

    def test_every_statement_check_names_a_real_line(self):
        """A check pointing at a missing item would silently never run."""
        Mapping = self.env['vn.report.mapping']
        rows = self.env['vn.fs.note.template.row'].search([
            ('item_id.template_id', '=', self.template.id),
            ('statement_check', '!=', False)])
        self.assertTrue(rows)
        for row in rows:
            form_code, _sep, code = row.statement_check.partition(':')
            mapping = Mapping.search([('form_code', '=', form_code),
                                      ('version', '=', 'TT133')])
            self.assertTrue(mapping, row.statement_check)
            self.assertIn(code.lstrip('-'), mapping.line_ids.mapped('code'),
                          row.statement_check)

    # -- first year: comparatives from the ledger ----------------------
    def test_balance_table_and_check_against_b01a(self):
        self._books()
        note = self._note(2026)
        note.action_compute()
        bank = self._row(note, 'V.1', 'bank')
        self.assertEqual((bank.current, bank.comparative), (440.0, 800.0))
        self.assertEqual(bank.comparative_origin, 'ledger')
        check = note.check_ids.filtered(
            lambda c: c.row_id == self._row(note, 'V.1', 'total'))
        self.assertEqual((check.state, check.expected), ('ok', 440.0))

    def test_fixed_assets_movement(self):
        """Cost 1,200 + 300 = 1,500; depreciation 200 + 250 = 450; carrying
        amount 1,000 + 300 − 250 = 1,050."""
        self._books()
        note = self._note(2026)
        note.action_compute()
        self.assertEqual(self._figures(note, 'V.5', 'a1'),
                         (1200.0, 300.0, 0.0, 1500.0))
        self.assertEqual(self._figures(note, 'V.5', 'a2'),
                         (200.0, 250.0, 0.0, 450.0))
        self.assertEqual(self._figures(note, 'V.5', 'a3'),
                         (1000.0, 300.0, 250.0, 1050.0))

    def test_tax_payable_and_paid(self):
        """VAT: opening 0, payable 100, paid 60, closing 40."""
        self._books()
        note = self._note(2026)
        note.action_compute()
        self.assertEqual(self._figures(note, 'V.10', 't33311'),
                         (0.0, 100.0, 60.0, 40.0))
        self.assertEqual(self._figures(note, 'V.10', 'total'),
                         (0.0, 100.0, 60.0, 40.0))

    def test_equity_reconciliation(self):
        """421: −200 at the start, +750 profit, 550 at the end; total equity
        1,800 → 2,550, which is B01a-DNN item 400."""
        self._books()
        note = self._note(2026)
        note.action_compute()
        self.assertEqual(self._figures(note, 'V.13', 'c6'),
                         (-200.0, 750.0, 0.0, 550.0))
        self.assertEqual(self._figures(note, 'V.13', 'c7'),
                         (1800.0, 750.0, 0.0, 2550.0))
        check = note.check_ids.filtered(
            lambda c: c.row_id == self._row(note, 'V.13', 'c7'))
        self.assertEqual(check.state, 'ok')

    def test_income_tables_leave_out_the_year_end_transfer(self):
        self._books()
        note = self._note(2026)
        note.action_compute()
        revenue = self._row(note, 'VI.1', 'a1')
        self.assertEqual((revenue.current, revenue.comparative), (1000.0, 0.0))
        self.assertEqual(self._row(note, 'VI.6', 'a').current, 250.0)
        self.assertEqual(self._row(note, 'VI.6', 'net').current, 250.0)

    def test_everything_agrees_with_the_statements(self):
        self._books()
        note = self._note(2026)
        note.action_compute()
        self.assertFalse(note.check_ids.filtered(
            lambda c: c.state == 'mismatch').mapped('name'))
        self.assertEqual(note.check_state, 'ok')
        self.assertTrue(note.check_ids.filtered(lambda c: c.state == 'ok'))

    def test_hand_edit_is_kept_and_flagged(self):
        """Goods typed in by hand: kept on recompute, and V.4 no longer
        agrees with B01a-DNN item 141."""
        self._books()
        note = self._note(2026)
        note.action_compute()
        goods = self._row(note, 'V.4', 'i156')
        goods.current = 5.0
        self.assertTrue(goods.manual)
        note.action_compute()
        self.assertEqual(goods.current, 5.0)
        self.assertEqual(self._row(note, 'V.4', 'total').current, 5.0)
        check = note.check_ids.filtered(
            lambda c: c.row_id == self._row(note, 'V.4', 'total'))
        self.assertEqual((check.state, check.difference), ('mismatch', 5.0))
        goods.action_reset()
        note.action_compute()
        self.assertEqual(goods.current, 0.0)

    def test_total_cannot_be_typed_over(self):
        self._books()
        note = self._note(2026)
        note.action_compute()
        with self.assertRaises(UserError):
            self._row(note, 'V.1', 'total').current = 1.0

    # -- second year: comparatives from last year's notes --------------
    def test_comparative_comes_from_last_years_notes(self):
        """Last year's notes say 777 for the bank (a restatement, say); the
        ledger says 800. The circular takes last year's notes."""
        self._books()
        last = self._note(2025)
        last.action_compute()
        self._row(last, 'V.1', 'bank').current = 777.0
        last.action_compute()
        last.action_lock()
        note = self._note(2026)
        self.assertEqual(note.previous_note_id, last)
        note.action_compute()
        bank = self._row(note, 'V.1', 'bank')
        self.assertEqual((bank.comparative, bank.comparative_origin),
                         (777.0, 'previous'))
        self.assertEqual(self._row(note, 'V.1', 'total').comparative, 777.0)

    def test_text_is_carried_over_but_dates_are_not(self):
        last = self._note(2025)
        item = last.item_ids.filtered(lambda i: i.reference == 'I.1')
        item.content = '<p>Công ty TNHH một thành viên</p>'
        last.action_compute()
        last.action_lock()
        note = self._note(2026)
        self.assertIn('Công ty TNHH một thành viên', str(
            note.item_ids.filtered(lambda i: i.reference == 'I.1').content))
        period = str(note.item_ids.filtered(
            lambda i: i.reference == 'II.1').content)
        self.assertIn('01/01/2026', period)
        self.assertIn('31/12/2026', period)

    # -- locking, security, printing -----------------------------------
    def test_locked_notes_cannot_change(self):
        self._books()
        note = self._note(2026)
        with self.assertRaises(UserError):
            note.action_lock()              # not computed yet
        note.action_compute()
        note.action_lock()
        with self.assertRaises(UserError):
            self._row(note, 'V.4', 'i156').current = 1.0
        with self.assertRaises(UserError):
            note.item_ids[:1].content = '<p>x</p>'
        with self.assertRaises(UserError):
            note.action_compute()
        with self.assertRaises(UserError):
            note.unlink()
        # Only the Unlock button, which checks the user's rights, unlocks.
        with self.assertRaises(UserError):
            note.write({'state': 'draft'})
        self.assertEqual(note.state, 'locked')

    @mute_logger('odoo.sql_db')
    def test_one_note_per_form_and_year(self):
        self._note(2026)
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self._note(2026)

    def test_other_company_notes_are_not_visible(self):
        other = self.company_data_2['company']
        other.vn_accounting_circular = 'TT133'
        foreign = self.env['vn.fs.note'].sudo().create({
            'company_id': other.id, 'template_id': self.template.id,
            'date_from': '2026-01-01', 'date_to': '2026-12-31'})
        visible = self.env['vn.fs.note'].with_context(
            allowed_company_ids=[self.company.id]).search([])
        self.assertNotIn(foreign, visible)

    def test_pdf_renders_the_form(self):
        self._books()
        note = self._note(2026)
        note.preparer_name = 'Nguyễn Văn A'
        note.action_compute()
        html = self.env['ir.actions.report']._render_qweb_html(
            'l10n_vn_vas_reports.report_fs_note', note.ids)[0]
        if isinstance(html, bytes):
            html = html.decode('utf-8')
        html = str(html)
        self.assertIn('B09-DNN', html)
        self.assertIn('BẢN THUYẾT MINH BÁO CÁO TÀI CHÍNH', html)
        self.assertIn('Ban hành theo Thông tư số 133/2016/TT-BTC', html)
        self.assertIn('NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT', html)
        self.assertIn('Nguyễn Văn A', html)
        self.assertIn('Tăng, giảm tài sản cố định', html)
        # Totals kept only for the checks are not printed.
        self.assertNotIn('Tổng chứng khoán kinh doanh', html)
