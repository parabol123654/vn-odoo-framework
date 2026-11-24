# -*- coding: utf-8 -*-
# Target: Odoo 20.0 Community Edition
"""Phiếu thu / phiếu chi: one continuous series per company and per year."""

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestCashVoucher(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data_2 = cls.setup_other_company()

    def _receipt(self, when, data=None):
        data = data or self.company_data
        journal = data['default_journal_cash']
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': when,
            'journal_id': journal.id,
            'line_ids': [
                (0, 0, {'account_id': journal.default_account_id.id,
                        'debit': 100.0, 'credit': 0.0, 'name': 'Thu tiền'}),
                (0, 0, {'account_id': data['default_account_revenue'].id,
                        'debit': 0.0, 'credit': 100.0, 'name': 'Thu tiền'}),
            ],
        })
        move.action_post()
        return move

    def test_number_follows_the_entry_year(self):
        self.assertEqual(self._receipt('2025-12-31').vn_voucher_number,
                         'PT/2025/00001')
        self.assertEqual(self._receipt('2026-01-02').vn_voucher_number,
                         'PT/2026/00001')
        self.assertEqual(self._receipt('2025-12-30').vn_voucher_number,
                         'PT/2025/00002')

    def test_each_company_has_its_own_series(self):
        self.assertEqual(self._receipt('2026-03-01').vn_voucher_number,
                         'PT/2026/00001')
        other = self._receipt('2026-03-01', self.company_data_2)
        self.assertEqual(other.vn_voucher_number, 'PT/2026/00001')

    def test_continues_numbers_issued_before_the_split(self):
        legacy = self._receipt('2024-05-01')
        legacy.vn_voucher_number = 'PT/2026/00007'
        self.assertEqual(self._receipt('2026-05-01').vn_voucher_number,
                         'PT/2026/00008')
