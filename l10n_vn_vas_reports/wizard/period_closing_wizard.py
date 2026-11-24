# -*- coding: utf-8 -*-
# Target: Odoo 20.0 Community Edition
"""Kết chuyển cuối kỳ: giảm trừ doanh thu, xác định kết quả kinh doanh.

Balances run from the start of the fiscal year to the closing date and include
earlier closing entries of that year, so a monthly closing followed by a
year-end one moves only what is left, and a second run finds nothing. They are
the selected company's own: a branch closes its own books.

The income statement leaves out every move touching 911 or 421 (the mapping's
closing expression), so the closing itself never changes it. Where the
deduction transfer goes depends on how the statement reads item 02:

* through the debit of 511 (TT200: "Nợ 511 đối ứng Có 521"), the transfer
  must be seen, so it is a move of its own, without 911;
* from 521 directly (TT99), the transfer must not be seen, or 521 would read
  zero, so its lines go into the closing move.

Labels are Vietnamese whatever the user's language: the entry is a line of the
statutory general journal.
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

from odoo.addons.vn_core.domain.financial_statement.expression import AccountExpression
from odoo.addons.vn_core.domain.ledger.calculators.period_closing import (
    PeriodClosingCalculator,
)

EXPRESSIONS = {
    # circular: (revenue, deduction, expense)
    "TT200": ("511*,515*,711*", "521*", "632*,635*,641*,642*,811*,821*"),
    "TT99": ("511*,515*,711*", "521*", "632*,635*,641*,642*,811*,821*"),
    "TT133": ("511*,515*,711*", "", "632*,635*,642*,811*,821*"),
}

ACCOUNT_DOMAIN = "[('company_ids', 'in', company_id)]"


class VnPeriodClosingWizard(models.TransientModel):
    """Posts the period-end closing entries of one company."""

    _name = "vn.period.closing.wizard"
    _description = "Period-End Closing"
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    date = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1)
        - timedelta(days=1),
    )
    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        check_company=True,
        domain="[('type', '=', 'general'), ('company_id', 'parent_of', company_id)]",
        compute="_compute_journal_id",
        store=True,
        readonly=False,
        precompute=True,
    )
    revenue_expression = fields.Char(
        compute="_compute_revenue_expression",
        store=True,
        readonly=False,
        precompute=True,
        help="Revenue and income accounts, e.g. 511*,515*,711*.",
    )
    deduction_expression = fields.Char(
        compute="_compute_deduction_expression",
        store=True,
        readonly=False,
        precompute=True,
        help="Sales deductions moved onto the sales account first. "
        "Empty under TT133, which has no account 521.",
    )
    expense_expression = fields.Char(
        compute="_compute_expense_expression",
        store=True,
        readonly=False,
        precompute=True,
        help="Cost and expense accounts closed to 911.",
    )
    sales_account_id = fields.Many2one(
        "account.account",
        string="Sales account (511)",
        required=True,
        check_company=True,
        domain=ACCOUNT_DOMAIN,
        compute="_compute_sales_account_id",
        store=True,
        readonly=False,
        precompute=True,
    )
    result_account_id = fields.Many2one(
        "account.account",
        string="Result account (911)",
        required=True,
        check_company=True,
        domain=ACCOUNT_DOMAIN,
        compute="_compute_result_account_id",
        store=True,
        readonly=False,
        precompute=True,
    )
    retained_account_id = fields.Many2one(
        "account.account",
        string="Retained earnings account (4212)",
        required=True,
        check_company=True,
        domain=ACCOUNT_DOMAIN,
        compute="_compute_retained_account_id",
        store=True,
        readonly=False,
        precompute=True,
    )

    # One compute per field: a field given at creation stops only its own
    # compute, so the others still get their defaults.
    def _expressions(self):
        return EXPRESSIONS.get(
            self.company_id.vn_accounting_circular, EXPRESSIONS["TT200"]
        )

    @api.depends("company_id")
    def _compute_revenue_expression(self):
        for wizard in self:
            wizard.revenue_expression = wizard._expressions()[0]

    @api.depends("company_id")
    def _compute_deduction_expression(self):
        for wizard in self:
            wizard.deduction_expression = wizard._expressions()[1]

    @api.depends("company_id")
    def _compute_expense_expression(self):
        for wizard in self:
            wizard.expense_expression = wizard._expressions()[2]

    @api.depends("company_id")
    def _compute_journal_id(self):
        for wizard in self:
            wizard.journal_id = self.env["account.journal"].search(
                [("company_id", "=", wizard.company_id.id), ("type", "=", "general")],
                limit=1,
            )

    @api.depends("company_id")
    def _compute_sales_account_id(self):
        for wizard in self:
            wizard.sales_account_id = wizard._first_account("5111%", "511%")

    @api.depends("company_id")
    def _compute_result_account_id(self):
        for wizard in self:
            wizard.result_account_id = wizard._first_account("911%")

    @api.depends("company_id")
    def _compute_retained_account_id(self):
        for wizard in self:
            wizard.retained_account_id = wizard._first_account("4212%", "421%")

    def _first_account(self, *patterns):
        accounts = self.env["account.account"].with_company(self.company_id)
        for pattern in patterns:
            account = accounts.search(
                [("company_ids", "in", self.company_id.id), ("code", "=like", pattern)],
                limit=1,
            )
            if account:
                return account
        return accounts

    # ------------------------------------------------------------------
    def _date_label(self):
        return self.date.strftime("%d/%m/%Y")

    def _resolve(self, expression):
        """-> accounts selected by ``expression``, deprecated ones included.

        A deprecated account that still carries a balance must be seen, or the
        closing would fail on it or leave it out.
        """
        accounts = self.env["account.account"].search(
            [("company_ids", "in", self.company_id.id)]
        )
        ids = [a.id for a in AccountExpression.resolve(expression, accounts)]
        return accounts.browse(ids)

    def _balances(self, accounts):
        company = self.company_id
        date_from = company.compute_fiscalyear_dates(self.date)["date_from"]
        groups = self.env["account.move.line"]._read_group(
            [
                ("company_id", "=", company.id),
                ("account_id", "in", accounts.ids),
                ("parent_state", "=", "posted"),
                ("date", ">=", date_from),
                ("date", "<=", self.date),
            ],
            ["account_id"],
            ["balance:sum"],
        )
        return {account.id: balance for account, balance in groups}

    def _check_deprecated(self, accounts, balances):
        currency = self.company_id.currency_id
        archived = accounts.filtered(
            lambda a: a.deprecated and not currency.is_zero(balances.get(a.id, 0.0))
        )
        if archived:
            raise UserError(
                _(
                    "Deprecated accounts still carry a balance for the year: %s; "
                    "reactivate them to close the period."
                )
                % ", ".join(archived.mapped("code"))
            )

    def _income_mapping(self):
        """The company's income statement mapping, or an empty recordset.

        A missing mapping does not block the closing: the deduction transfer
        then gets its own move, which suits a statement reading 511's debit.
        """
        try:
            return self.env["vn.report.mapping"].default_for(
                "income_statement", self.company_id
            )
        except UserError:
            return self.env["vn.report.mapping"]

    def _check_excluded(self, mapping):
        """911 and 4212 must be in the mapping's closing expression.

        Otherwise the income statement reads the closing entry as revenue and
        expense, and every line of it falls to zero after closing.
        """
        if not mapping:
            return
        accounts = self.result_account_id | self.retained_account_id
        excluded = AccountExpression.resolve(mapping.closing_expression, accounts)
        missing = accounts - accounts.browse([a.id for a in excluded])
        if missing:
            raise UserError(
                _(
                    "The income statement %(mapping)s does not leave out "
                    "entries on %(accounts)s, so it would read zero after "
                    "closing. Choose other accounts, or add them to the "
                    "mapping's closing expression."
                )
                % {
                    "mapping": mapping.display_name,
                    "accounts": ", ".join(missing.mapped("code")),
                }
            )

    def _statement_reads(self, mapping, accounts):
        """True when the income statement maps any of ``accounts``."""
        return any(
            AccountExpression.resolve(line.expression, accounts)
            for line in mapping.line_ids
            if line.expression
        )

    def _move(self, ref, lines):
        accounts = self.env["account.account"].browse(
            sorted({line[0] for line in lines})
        )
        codes = {a.id: a.code for a in accounts}
        line_ids = []
        # Lines come in pairs, source first: label both "from X to Y".
        for (source, amount), (target, counter) in zip(lines[::2], lines[1::2]):
            label = "Kết chuyển %s sang %s" % (codes[source], codes[target])
            line_ids += [
                Command.create(
                    {"account_id": source, "balance": amount, "name": label}
                ),
                Command.create(
                    {"account_id": target, "balance": counter, "name": label}
                ),
            ]
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": self.date,
                "journal_id": self.journal_id.id,
                "ref": ref,
                "line_ids": line_ids,
            }
        )
        move.action_post()
        return move

    def action_post(self):
        """Post the deduction transfer and the closing entry, then open them."""
        self.ensure_one()
        return self.with_company(self.company_id)._post()

    def _post(self):
        rounding = self.company_id.currency_id.rounding
        deductions = self._resolve(self.deduction_expression)
        closed = (
            self._resolve(self.revenue_expression)
            | self._resolve(self.expense_expression)
            | self.sales_account_id
        )
        balances = self._balances(deductions | closed | self.result_account_id)
        self._check_deprecated(deductions | closed, balances)

        deduction = PeriodClosingCalculator.deduction_transfer(
            balances, deductions.ids, self.sales_account_id.id, rounding
        )
        balances = PeriodClosingCalculator.apply(balances, deduction)
        closing = PeriodClosingCalculator.closing(
            balances,
            closed.ids,
            self.result_account_id.id,
            self.retained_account_id.id,
            rounding,
        )
        if not deduction and not closing:
            raise UserError(
                _(
                    "Nothing to transfer: every revenue and expense account is "
                    "already at zero on %s."
                )
                % self._date_label()
            )
        mapping = self._income_mapping()
        self._check_excluded(mapping)

        if deduction and mapping and self._statement_reads(mapping, deductions):
            closing, deduction = deduction + closing, ()
        moves = self.env["account.move"]
        if deduction:
            moves |= self._move(
                "Kết chuyển giảm trừ doanh thu %s" % self._date_label(), deduction
            )
        if closing:
            moves |= self._move(
                "Kết chuyển xác định kết quả kinh doanh %s" % self._date_label(),
                closing,
            )

        action = {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "name": _("Closing Entries"),
        }
        if len(moves) == 1:
            return dict(action, res_id=moves.id, view_mode="form")
        return dict(action, domain=[("id", "in", moves.ids)], view_mode="list,form")
