# -*- coding: utf-8 -*-
# Target: Odoo 20.0 Community Edition
# Test conventions: unittest names (setUpClass), self-describing test
# names, and calls to the wizards' private helpers under test.
# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=invalid-name,protected-access
"""Period-end closing entries (kết chuyển cuối kỳ): 521 → 511, revenue and
expenses → 911, 911 → 4212.

The generic test chart has no Vietnamese codes, so the VN accounts are created
here with 6-digit codes that the shipped TT200 B02-DN expressions (511*, 632*,
...) pick up.
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.vn_core.dto.filters import LedgerFilter

CLOSING_DATE = "2026-12-31"


@tagged("post_install", "-at_install")
class TestPeriodClosing(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Where the deduction transfer goes depends on the circular's B02.
        cls.env.company.vn_accounting_circular = "TT200"
        account = cls.env["account.account"]

        def create(code, name, account_type):
            return account.create(
                {"code": code, "name": name, "account_type": account_type}
            )

        cls.acc_511 = create("511100", "Doanh thu bán hàng hóa", "income")
        cls.acc_515 = create("515100", "Doanh thu hoạt động tài chính", "income_other")
        cls.acc_521 = create("521100", "Chiết khấu thương mại", "income")
        cls.acc_632 = create("632100", "Giá vốn hàng bán", "expense_direct_cost")
        cls.acc_642 = create("642100", "Chi phí quản lý doanh nghiệp", "expense")
        cls.acc_911 = create("911000", "Xác định kết quả kinh doanh", "equity")
        cls.acc_4212 = create(
            "421200", "Lợi nhuận sau thuế chưa phân phối năm nay", "equity"
        )
        cls.in_scope = (
            cls.acc_511 | cls.acc_515 | cls.acc_521 | cls.acc_632 | cls.acc_642
        )

        cls.journal = cls.company_data["default_journal_misc"]
        cls.receivable = cls.company_data["default_account_receivable"]

        # Previous fiscal year: must never be transferred.
        cls._entry(cls.receivable, cls.acc_511, 500.0, "2025-06-30")
        # This year: revenue 1,000 + financial income 30, cost 600, admin 150.
        cls._entry(cls.receivable, cls.acc_511, 1000.0, "2026-03-01")
        cls._entry(cls.receivable, cls.acc_515, 30.0, "2026-03-05")
        cls._entry(cls.acc_632, cls.receivable, 600.0, "2026-04-01")
        cls._entry(cls.acc_642, cls.receivable, 150.0, "2026-05-01")
        cls.profit = 280.0

        cls.engine = cls.env["vn.ledger.provider"].build_financial_statement_engine()

    # ------------------------------------------------------------------
    @classmethod
    def _entry(cls, debit_account, credit_account, amount, when):
        move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": when,
                "journal_id": cls.journal.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": debit_account.id,
                            "name": "test",
                            "debit": amount,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": credit_account.id,
                            "name": "test",
                            "debit": 0.0,
                            "credit": amount,
                        },
                    ),
                ],
            }
        )
        move.action_post()
        return move

    def _balance(self, account, date_from="2026-01-01", date_to=CLOSING_DATE):
        lines = self.env["account.move.line"].search(
            [
                ("account_id", "=", account.id),
                ("company_id", "=", self.env.company.id),
                ("parent_state", "=", "posted"),
                ("date", ">=", date_from),
                ("date", "<=", date_to),
            ]
        )
        return self.env.company.currency_id.round(sum(lines.mapped("balance")))

    def _wizard(self, **values):
        vals = {
            "date": CLOSING_DATE,
            "journal_id": self.journal.id,
            "revenue_expression": "511*,515*,711*",
            "deduction_expression": "521*",
            "expense_expression": "632*,635*,641*,642*,811*,821*",
            "sales_account_id": self.acc_511.id,
            "result_account_id": self.acc_911.id,
            "retained_account_id": self.acc_4212.id,
        }
        vals.update(values)
        return self.env["vn.period.closing.wizard"].create(vals)

    def _close(self, **values):
        action = self._wizard(**values).action_post()
        return self._moves(action)

    def _moves(self, action):
        moves = self.env["account.move"]
        if action.get("res_id"):
            return moves.browse(action["res_id"])
        self.assertTrue(action.get("domain"), "the action must open the posted move(s)")
        return moves.search(action["domain"])

    def _statement(
        self, date_from="2026-01-01", date_to=CLOSING_DATE, mapping="tt200_b02dn"
    ):
        report = self.engine.compute(
            LedgerFilter(
                date_from=date.fromisoformat(date_from),
                date_to=date.fromisoformat(date_to),
                company_ids=(self.env.company.id,),
            ),
            mapping,
        )
        return {line.code: line.amount for line in report.lines}

    # ------------------------------------------------------------------
    def test_revenue_and_expenses_end_at_zero(self):
        self._close()
        for account in self.in_scope:
            self.assertEqual(self._balance(account), 0.0, account.code)
        self.assertEqual(self._balance(self.acc_911), 0.0)

    def test_profit_is_credited_to_4212(self):
        self.assertEqual(self._balance(self.acc_4212), 0.0)
        self._close()
        self.assertEqual(self._balance(self.acc_4212), -self.profit)

    def test_posts_one_move_on_the_journal_and_date(self):
        moves = self._close()
        self.assertEqual(len(moves), 1, "no deduction: only the 911 entry")
        self.assertEqual(moves.state, "posted")
        self.assertEqual(moves.journal_id, self.journal)
        self.assertEqual(moves.date, date(2026, 12, 31))
        self.assertTrue(
            all(moves.line_ids.mapped("name")), "every line carries a label"
        )
        self.assertEqual(sum(moves.line_ids.mapped("balance")), 0.0)

    def test_previous_fiscal_year_is_untouched(self):
        before_2025 = self._statement("2025-01-01", "2025-12-31")
        self._close()
        self.assertEqual(
            self._balance(self.acc_511, "2025-01-01", "2025-12-31"), -500.0
        )
        self.assertEqual(
            self._balance(self.acc_511, "2000-01-01", CLOSING_DATE), -500.0
        )
        self.assertEqual(self._statement("2025-01-01", "2025-12-31"), before_2025)
        # Nothing of 2025 found its way into 4212 either.
        self.assertEqual(self._balance(self.acc_4212), -self.profit)

    def test_second_run_finds_nothing(self):
        self._close()
        with self.assertRaises(UserError):
            self._close()

    def test_nothing_to_close_raises(self):
        with self.assertRaises(UserError):
            self._close(date="2026-01-31")

    def test_loss_is_debited_to_4212(self):
        self._entry(self.acc_642, self.receivable, 1000.0, "2026-06-15")
        self._close()
        loss = 1000.0 - self.profit
        self.assertEqual(self._balance(self.acc_4212), loss)
        self.assertEqual(self._balance(self.acc_911), 0.0)
        for account in self.in_scope:
            self.assertEqual(self._balance(account), 0.0, account.code)

    def test_income_statement_is_identical_before_and_after(self):
        before = self._statement()
        self.assertEqual(before["01"], 1000.0)
        self.assertEqual(before["11"], 600.0)
        self.assertEqual(before["60"], self.profit)
        self._close()
        after = self._statement()
        self.assertEqual(after, before)

    def test_deduction_is_transferred_in_its_own_move(self):
        """Nợ 511 / Có 521 is kept apart from the 911 entry, so B02 line 02
        reads it on the debit side of 511."""
        self._entry(self.acc_521, self.receivable, 100.0, "2026-06-01")
        profit = self.profit - 100.0

        moves = self._close()
        self.assertEqual(len(moves), 2)
        deduction = moves.filtered(lambda m: self.acc_521 in m.line_ids.account_id)
        self.assertEqual(len(deduction), 1)
        self.assertEqual(deduction.line_ids.account_id, self.acc_511 | self.acc_521)
        self.assertEqual(
            sum(
                deduction.line_ids.filtered(
                    lambda line: line.account_id == self.acc_511
                ).mapped("balance")
            ),
            100.0,
        )
        closing = moves - deduction
        self.assertIn(self.acc_911, closing.line_ids.account_id)
        self.assertIn(self.acc_4212, closing.line_ids.account_id)

        for account in self.in_scope:
            self.assertEqual(self._balance(account), 0.0, account.code)
        self.assertEqual(self._balance(self.acc_911), 0.0)
        self.assertEqual(self._balance(self.acc_4212), -profit)

        after = self._statement()
        self.assertEqual(after["01"], 1000.0)
        self.assertEqual(after["02"], 100.0)
        self.assertEqual(after["10"], 900.0)
        self.assertEqual(after["60"], profit)

    def test_deduction_closing_leaves_the_statement_unchanged(self):
        """Once 521 is in 511 the 911 entry itself changes nothing on B02."""
        self._entry(self.acc_521, self.receivable, 100.0, "2026-06-01")
        # The accountant already moved 521 into 511 by hand.
        self._entry(self.acc_511, self.acc_521, 100.0, "2026-12-31")
        before = self._statement()
        self.assertEqual(before["02"], 100.0)
        moves = self._close()
        self.assertEqual(len(moves), 1, "521 is already at zero")
        self.assertEqual(self._statement(), before)

    # ------------------------------------------------------------------
    def test_tt99_deduction_goes_into_the_closing_move(self):
        """TT99 B02 item 02 reads 521 itself: the transfer must stay out of
        the statement, so it is part of the 911 entry."""
        self.env.company.vn_accounting_circular = "TT99"
        self._entry(self.acc_521, self.receivable, 100.0, "2026-06-01")
        before = self._statement(mapping="tt99_b02dn")
        self.assertEqual(before["01"], 1000.0)
        self.assertEqual(before["02"], 100.0)
        self.assertEqual(before["10"], 900.0)

        moves = self._close()
        self.assertEqual(len(moves), 1)
        accounts = moves.line_ids.account_id
        for account in (self.acc_521, self.acc_511, self.acc_911):
            self.assertIn(account, accounts, account.code)

        self.assertEqual(self._statement(mapping="tt99_b02dn"), before)
        for account in self.in_scope:
            self.assertEqual(self._balance(account), 0.0, account.code)
        self.assertEqual(self._balance(self.acc_911), 0.0)
        self.assertEqual(self._balance(self.acc_4212), -(self.profit - 100.0))

    def test_existing_911_balance_is_closed_to_4212(self):
        """A manual Nợ 511 / Có 911 during the year is part of the result."""
        self._entry(self.acc_511, self.acc_911, 300.0, "2026-06-30")
        self.assertEqual(self._balance(self.acc_911), -300.0)
        self._close()
        self.assertEqual(self._balance(self.acc_911), 0.0)
        self.assertEqual(self._balance(self.acc_4212), -self.profit)
        for account in self.in_scope:
            self.assertEqual(self._balance(account), 0.0, account.code)

    # Before 19.0 an account is archived by deprecating it: account.account
    # has no ``active`` field.
    def test_deprecated_account_with_a_balance_is_refused(self):
        acc_711 = self.env["account.account"].create(
            {"code": "711100", "name": "Thu nhập khác", "account_type": "income_other"}
        )
        self._entry(self.receivable, acc_711, 40.0, "2026-07-01")
        acc_711.deprecated = True
        with self.assertRaises(UserError):
            self._close()

    def test_deprecated_account_at_zero_does_not_block(self):
        acc_811 = self.env["account.account"].create(
            {"code": "811100", "name": "Chi phí khác", "account_type": "expense"}
        )
        self._entry(acc_811, self.receivable, 40.0, "2026-02-01")
        self._entry(self.receivable, acc_811, 40.0, "2026-02-02")
        acc_811.deprecated = True
        self._close()
        self.assertEqual(self._balance(acc_811), 0.0)
        self.assertEqual(self._balance(self.acc_4212), -self.profit)

    def test_non_calendar_fiscal_year(self):
        """Fiscal year April-March: closing at 2026-12-31 covers April 2026
        onwards; February (previous fiscal year) stays where it is."""
        self.env.company.write(
            {"fiscalyear_last_month": "3", "fiscalyear_last_day": 31}
        )
        self._entry(self.receivable, self.acc_511, 70.0, "2026-02-15")
        self._entry(self.receivable, self.acc_511, 200.0, "2026-05-10")
        fy_from, prev_from, prev_to = "2026-04-01", "2025-04-01", "2026-03-31"

        moves = self._close()
        # Current fiscal year: 511 -200, 632 +600, 642 +150 -> loss 550.
        for account in self.in_scope:
            self.assertEqual(self._balance(account, fy_from), 0.0, account.code)
        self.assertEqual(self._balance(self.acc_911, fy_from), 0.0)
        self.assertEqual(self._balance(self.acc_4212, fy_from), 550.0)
        # Previous fiscal year untouched: 511 -1,070 (with 2025-06-30's -500
        # it is -1,570), 515 -30 in March, not closed at all.
        self.assertEqual(self._balance(self.acc_511, prev_from, prev_to), -1570.0)
        self.assertEqual(self._balance(self.acc_515, prev_from, prev_to), -30.0)
        self.assertNotIn(self.acc_515, moves.line_ids.account_id)

    def test_defaults_follow_the_circular(self):
        company = self.env.company
        company.vn_accounting_circular = "TT133"
        wizard = self.env["vn.period.closing.wizard"].create({"date": CLOSING_DATE})
        self.assertEqual(wizard.expense_expression, "632*,635*,642*,811*,821*")
        self.assertFalse(wizard.deduction_expression)
        self.assertEqual(wizard.revenue_expression, "511*,515*,711*")

        company.vn_accounting_circular = "TT200"
        wizard = self.env["vn.period.closing.wizard"].create({"date": CLOSING_DATE})
        self.assertEqual(wizard.deduction_expression, "521*")
        self.assertEqual(wizard.expense_expression, "632*,635*,641*,642*,811*,821*")

    def test_result_account_outside_the_closing_expression_is_refused(self):
        """B02 leaves out only moves touching 911*/421*: closing through any
        other account would show up on the statement."""
        acc_999 = self.env["account.account"].create(
            {"code": "999000", "name": "Not a result account", "account_type": "equity"}
        )
        with self.assertRaises(UserError):
            self._close(result_account_id=acc_999.id)
        self.assertEqual(self._balance(self.acc_511), -1000.0)
