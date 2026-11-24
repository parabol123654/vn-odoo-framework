# -*- coding: utf-8 -*-
# Target: Odoo 19.0 Community Edition
"""Phiếu thu (01-TT) và Phiếu chi (02-TT).

Every cash movement in Vietnam needs a numbered, signed voucher — a receipt when
money comes in, a payment slip when it goes out. Odoo has no such document.

**No new model.** A cash voucher *is* a journal entry on a cash journal; giving
it a model of its own would mean two records for one economic event and a
lifetime of keeping them in step. So ``account.move`` gains a voucher type and a
voucher number, and the entry prints as the statutory form.

That also closes a gap flagged earlier: Sổ quỹ tiền mặt (S07-DN) is supposed to
carry the voucher number, not the journal entry name. Now it can.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

RECEIPT, PAYMENT = 'receipt', 'payment'


class AccountMove(models.Model):
    _inherit = 'account.move'

    vn_voucher_type = fields.Selection(
        [(RECEIPT, 'Phiếu thu'), (PAYMENT, 'Phiếu chi')],
        string='Cash voucher', compute='_compute_vn_voucher_type', store=True,
        help="Set automatically for entries on a cash journal: a receipt when "
             "cash is debited, a payment when it is credited.")
    vn_voucher_number = fields.Char(
        string='Voucher number', copy=False, readonly=True, index=True,
        help="Assigned from its own sequence when the entry is posted, "
             "independently of the journal entry name.")

    @api.depends('journal_id', 'line_ids.debit', 'line_ids.credit',
                 'line_ids.account_id')
    def _compute_vn_voucher_type(self):
        """Direction of the cash, not of the document.

        A refund to a customer sits on a sales-shaped entry and is still money
        leaving the till, so the type follows the balance on the cash account
        rather than the move type.
        """
        for move in self:
            move.vn_voucher_type = False
            if move.journal_id.type != 'cash':
                continue
            balance = sum(
                line.balance for line in move.line_ids
                if line.account_id.account_type == 'asset_cash')
            if move.currency_id.is_zero(balance):
                continue
            move.vn_voucher_type = RECEIPT if balance > 0 else PAYMENT

    # ------------------------------------------------------------------
    def _vn_voucher_sequence_code(self):
        self.ensure_one()
        return ('l10n_vn.cash.receipt' if self.vn_voucher_type == RECEIPT
                else 'l10n_vn.cash.payment')

    def _vn_voucher_sequence(self):
        """The company's own series, copied from the shared template once.

        Each company keeps its own continuous series, so the template
        (``company_id`` empty) is never drawn from directly.
        """
        self.ensure_one()
        code = self._vn_voucher_sequence_code()
        sequences = self.env['ir.sequence'].sudo()
        sequence = sequences.search(
            [('code', '=', code), ('company_id', '=', self.company_id.id)],
            limit=1)
        if sequence:
            return sequence
        template = sequences.search(
            [('code', '=', code), ('company_id', '=', False)], limit=1)
        if not template:
            raise UserError(_(
                "No sequence found for %s. Check Settings > Technical > "
                "Sequences.") % code)
        return template.copy({
            'name': '%s - %s' % (template.name, self.company_id.name),
            'company_id': self.company_id.id,
            'prefix': (template.prefix or '').replace(
                '%(year)s', '%(range_year)s'),
            'use_date_range': True,
            'implementation': 'no_gap',
            'number_next': 1,
        })

    def _vn_voucher_open_year(self, sequence):
        """Create the year's range, continuing numbers already issued.

        Numbers issued before the series was split per company and per year
        carry the same prefix, so the new range starts after the highest one
        of this company to avoid issuing a number twice.
        """
        self.ensure_one()
        date_range = sequence._create_date_range_seq(self.date)
        prefix = sequence._get_prefix_suffix(
            date=self.date, date_range=date_range.date_from)[0]
        self.flush_model(['company_id', 'vn_voucher_type', 'vn_voucher_number'])
        self.env.cr.execute(
            r"""
            SELECT MAX(SUBSTRING(vn_voucher_number FROM '(\d+)\D*$')::bigint)
              FROM account_move
             WHERE company_id = %s
               AND vn_voucher_type = %s
               AND vn_voucher_number LIKE %s
            """,
            (self.company_id.id, self.vn_voucher_type,
             prefix.replace('\\', '\\\\').replace('%', r'\%')
             .replace('_', r'\_') + '%'))
        last = self.env.cr.fetchone()[0]
        if last:
            date_range.number_next = last + 1

    def _assign_vn_voucher_number(self):
        """Number a voucher once, at posting, in the year of its date.

        Numbering a draft would leave gaps in a statutory sequence whenever an
        entry is discarded, and a gap in a cash voucher series is what an
        inspector asks about first.
        """
        for move in self:
            if not move.vn_voucher_type or move.vn_voucher_number:
                continue
            sequence = move._vn_voucher_sequence()
            if sequence.use_date_range and not sequence.date_range_ids.filtered(
                    lambda r, d=move.date: r.date_from <= d <= r.date_to):
                move._vn_voucher_open_year(sequence)
            move.vn_voucher_number = sequence.with_context(
                ir_sequence_date=move.date).next_by_id(sequence_date=move.date)

    def action_post(self):
        result = super().action_post()
        self._assign_vn_voucher_number()
        return result

    def action_print_vn_voucher(self):
        self.ensure_one()
        if not self.vn_voucher_type:
            raise UserError(_(
                "This entry is not a cash voucher: it is not on a cash journal, "
                "or it does not move cash."))
        return self.env.ref(
            'l10n_vn_vas_reports.action_report_cash_voucher').report_action(self)

    # ------------------------------------------------------------------
    def _vn_voucher_counterparts(self):
        """Lines facing the cash, which is what the form lists.

        A voucher states who paid or was paid, how much, and against what — the
        cash line itself is the total, so the body of the form is everything
        else.
        """
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.account_id.account_type != 'asset_cash')

    def _vn_voucher_amount(self):
        self.ensure_one()
        return abs(sum(
            line.balance for line in self.line_ids
            if line.account_id.account_type == 'asset_cash'))
