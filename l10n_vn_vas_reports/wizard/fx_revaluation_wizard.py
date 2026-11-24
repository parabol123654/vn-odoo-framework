# -*- coding: utf-8 -*-
# Target: Odoo 20.0 Community Edition
"""Đánh giá lại các khoản mục tiền tệ có gốc ngoại tệ cuối kỳ.

The difference is booked against 413 and its net transferred to 515 (gain)
or 635 (loss) in the same entry, so 413 ends the period at zero. The entry is
reversed the next day: Odoo computes the realised difference of a later
payment from the invoice's own rate, and keeping the revaluation would count
the same difference twice.
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.vn_core.domain.ledger.calculators.revaluation import (
    PAYABLE, RECEIVABLE, RevaluationCalculator,
)

SIDES = {'receivable': RECEIVABLE, 'payable': PAYABLE}


class VnFxRevaluationWizard(models.TransientModel):
    _name = 'vn.fx.revaluation.wizard'
    _description = 'Foreign Currency Revaluation'

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    date = fields.Date(required=True, default=fields.Date.context_today)
    journal_id = fields.Many2one(
        'account.journal', required=True, domain=[('type', '=', 'general')],
        default=lambda self: self.env.company.currency_exchange_journal_id)
    account_ids = fields.Many2many(
        'account.account', string='Accounts', required=True,
        default=lambda self: self._default_accounts(),
        help="Monetary items only: cash, bank, receivables, payables, loans.")
    revaluation_account_id = fields.Many2one(
        'account.account', string='Exchange difference account (413)',
        required=True, default=lambda self: self._default_413())
    gain_account_id = fields.Many2one(
        'account.account', string='Gain account (515)', required=True,
        default=lambda self: self.env.company.income_currency_exchange_account_id)
    loss_account_id = fields.Many2one(
        'account.account', string='Loss account (635)', required=True,
        default=lambda self: self.env.company.expense_currency_exchange_account_id)
    rate_ids = fields.One2many('vn.fx.revaluation.rate', 'wizard_id',
                               string='Closing rates')

    @api.model
    def _default_accounts(self):
        return self.env['account.account'].search([
            ('company_id', '=', self.env.company.id),
            ('internal_type', 'in', ('liquidity', 'receivable',
                                     'payable')),
        ])

    @api.model
    def _default_413(self):
        accounts = self.env['account.account']
        for pattern in ('4131%', '413%'):
            account = accounts.search([
                ('company_id', '=', self.env.company.id),
                ('code', '=like', pattern)], limit=1)
            if account:
                return account
        return accounts

    # ------------------------------------------------------------------
    def _balances(self):
        company = self.company_id
        groups = self.env['account.move.line'].read_group(
            [('company_id', '=', company.id),
             ('account_id', 'in', self.account_ids.ids),
             ('currency_id', '!=', company.currency_id.id),
             ('parent_state', '=', 'posted'),
             ('date', '<=', self.date)],
            ['amount_currency:sum', 'balance:sum'],
            ['account_id', 'partner_id', 'currency_id'], lazy=False)
        return {(row['account_id'][0],
                 row['partner_id'][0] if row['partner_id'] else None,
                 row['currency_id'][0]):
                (row['amount_currency'], row['balance'])
                for row in groups}

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    def action_load_rates(self):
        """One line per currency held, at Odoo's rate for the date."""
        self.ensure_one()
        company = self.company_id
        currencies = self.env['res.currency'].browse(
            sorted({key[2] for key in self._balances()}))
        self.rate_ids = [(5, 0, 0)] + [
            (0, 0, {
                'currency_id': currency.id,
                'rate': currency._convert(1.0, company.currency_id, company,
                                          self.date, round=False)})
            for currency in currencies]
        return self._reopen()

    def action_post(self):
        self.ensure_one()
        rates = {line.currency_id.id: line.rate for line in self.rate_ids}
        balances = self._balances()
        missing = {key[2] for key in balances} - set(rates)
        if missing:
            raise UserError(_("Load the closing rates first: no rate for %s.")
                            % ', '.join(self.env['res.currency'].browse(
                                sorted(missing)).mapped('name')))
        differences = RevaluationCalculator.differences(
            balances, rates, self.company_id.currency_id.rounding,
            {a.id: SIDES[a.internal_type] for a in self.account_ids
             if a.internal_type in SIDES})
        if not differences:
            raise UserError(_("Every balance is already at the closing rate."))

        label = _('Exchange rate revaluation %s') % self.date
        total = sum(differences.values())
        result_account = self.gain_account_id if total > 0 else self.loss_account_id
        line_ids = [
            (0, 0, {
                'account_id': account_id, 'partner_id': partner_id,
                'currency_id': currency_id, 'amount_currency': 0.0,
                'debit': max(difference, 0.0),
                'credit': max(-difference, 0.0), 'name': label})
            for (account_id, partner_id, currency_id), difference
            in differences.items()
        ] + [
            (0, 0, {'account_id': self.revaluation_account_id.id,
                            'debit': max(-total, 0.0),
                            'credit': max(total, 0.0), 'name': label}),
            (0, 0, {'account_id': self.revaluation_account_id.id,
                            'debit': max(total, 0.0),
                            'credit': max(-total, 0.0),
                            'name': _('Net exchange difference transferred')}),
            (0, 0, {'account_id': result_account.id,
                            'debit': max(-total, 0.0),
                            'credit': max(total, 0.0),
                            'name': _('Net exchange difference transferred')}),
        ]
        move = self.env['account.move'].create({
            'move_type': 'entry', 'date': self.date,
            'journal_id': self.journal_id.id, 'ref': label,
            'line_ids': line_ids,
        })
        move.action_post()
        move._reverse_moves([{
            'date': self.date + timedelta(days=1),
            'ref': _('Reversal of %s') % label,
        }], cancel=True)
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move',
                'res_id': move.id, 'view_mode': 'form'}


class VnFxRevaluationRate(models.TransientModel):
    _name = 'vn.fx.revaluation.rate'
    _description = 'Foreign Currency Revaluation Rate'

    wizard_id = fields.Many2one('vn.fx.revaluation.wizard', required=True,
                                ondelete='cascade')
    currency_id = fields.Many2one('res.currency', required=True)
    rate = fields.Float(
        string='Closing rate', digits=(16, 6), required=True,
        help="Company currency per one unit, e.g. the bank's average transfer "
             "rate on the closing date.")
