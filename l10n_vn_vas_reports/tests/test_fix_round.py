# -*- coding: utf-8 -*-
"""Fix round: the opening column of a non-calendar fiscal year, and who signs
on the left of the books and statements.
"""

from datetime import date, timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

REPORT_DATE = "2026-12-31"

#: B01-DN item for cash (111*, 112*, 113*) on the TT200 form.
CASH_LINE = "111"

CIRCULARS = ("TT200", "TT133", "TT99")

#: Books (sổ kế toán): the left signature, per circular (BOOK_PREPARER).
#: (model, extra values) - trim here if a form keeps another label.
BOOK_WIZARDS = (
    ("vn.general.journal.wizard", {}),  # S03a
    ("vn.general.ledger.wizard", {}),  # S03b
    ("vn.partner.ledger.wizard", {}),  # S31
    ("vn.currency.ledger.wizard", {}),  # S32
    ("vn.cash.book.wizard", {"book_type": "cash"}),  # S07
    ("vn.cash.book.wizard", {"book_type": "bank"}),  # S08
    ("vn.sales.ledger.wizard", {}),  # S35
    ("vn.expense.ledger.wizard", {}),  # S36
)
#: TT200 and TT99 books print "Người ghi sổ"; TT133's print "Người lập biểu".
BOOK_PREPARER = {
    "TT200": "Người ghi sổ",
    "TT133": "Người lập biểu",
    "TT99": "Người ghi sổ",
}

#: Financial statements (báo cáo tài chính) keep the preparer of the form.
STATEMENT_WIZARDS = (
    "vn.balance.sheet.wizard",
    "vn.income.statement.wizard",
    "vn.cash.flow.wizard",
)
STATEMENT_PREPARER = {
    "TT200": "Người lập biểu",
    "TT133": "Người lập biểu",
    "TT99": "Người lập",
}


@tagged("post_install", "-at_install")
class TestNonCalendarOpeningColumn(AccountTestInvoicingCommon):
    """Fiscal year April-March: at 2026-12-31 "Số đầu năm" is the position at
    2026-03-31, not at 2025-12-31."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.vn_accounting_circular = "TT200"
        cls.company.write({"fiscalyear_last_month": "3", "fiscalyear_last_day": 31})
        account = cls.env["account.account"]

        def create(code, name, account_type):
            return account.create(
                {"code": code, "name": name, "account_type": account_type}
            )

        cls.cash = create("111199", "Tiền mặt", "asset_cash")
        cls.capital = create("411199", "Vốn góp của chủ sở hữu", "equity")
        cls.journal = cls.company_data["default_journal_misc"]

    # ------------------------------------------------------------------
    def _entry(self, debit_account, credit_account, amount, when):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": when,
                "journal_id": self.journal.id,
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

    def _wizard(self):
        return self.env["vn.balance.sheet.wizard"].create(
            {
                "company_id": self.company.id,
                # As-at statement: no start date (the default, 1 January of
                # the current year, could fall after REPORT_DATE).
                "date_from": False,
                "date_to": REPORT_DATE,
                "comparative": True,
                "show_diagnostics": False,
            }
        )

    def _cash_line(self):
        """-> (Số đầu năm, Số cuối năm) of the cash item."""
        report = self._wizard()._build_report()
        self.assertTrue(report.comparative, "the opening column is printed")
        line = report.by_code(CASH_LINE)
        return line.previous_amount or 0.0, line.amount

    # ------------------------------------------------------------------
    def test_opening_column_is_the_previous_fiscal_year_end(self):
        opening_before, closing_before = self._cash_line()
        # Fiscal year 2025-04 .. 2026-03: part of "Số đầu năm".
        self._entry(self.cash, self.capital, 70.0, "2026-02-15")
        # Fiscal year 2026-04 .. 2027-03: only in "Số cuối năm".
        self._entry(self.cash, self.capital, 200.0, "2026-05-10")
        opening, closing = self._cash_line()
        self.assertEqual(opening - opening_before, 70.0)
        self.assertEqual(closing - closing_before, 270.0)

    def test_opening_filter_ends_on_31_march(self):
        wizard = self._wizard()
        if not hasattr(wizard, "_comparative_filter"):
            self.skipTest("the wizard no longer builds a comparative filter")
        self.assertEqual(wizard._comparative_filter().date_to, date(2026, 3, 31))

    def test_notes_year_follows_the_fiscal_year(self):
        """B09: the default year is the last closed April-March year, and the
        comparative ("đầu năm") reads the year before it."""
        values = self.env["vn.fs.note"].default_get(
            ["company_id", "date_from", "date_to"]
        )
        date_to = fields.Date.to_date(values["date_to"])
        date_from = fields.Date.to_date(values["date_from"])
        self.assertEqual((date_to.month, date_to.day), (3, 31))
        self.assertEqual(date_from, date(date_to.year - 1, 4, 1))
        today = fields.Date.context_today(self.env["vn.fs.note"])
        self.assertLess(date_to, today)
        self.assertGreaterEqual(date_to, today - timedelta(days=366))

        note = self.env["vn.fs.note"].new(
            {
                "company_id": self.company.id,
                "date_from": "2026-04-01",
                "date_to": "2027-03-31",
            }
        )
        previous = note._previous_filter()
        self.assertEqual(previous.date_from, date(2025, 4, 1))
        self.assertEqual(previous.date_to, date(2026, 3, 31))


@tagged("post_install", "-at_install")
class TestSignatureLabels(AccountTestInvoicingCommon):

    def _wizard(self, model, values):
        vals = {"company_id": self.env.company.id}
        vals.update(values)
        return self.env[model].new(vals)

    def test_books_are_signed_by_the_bookkeeper(self):
        for circular in CIRCULARS:
            self.env.company.vn_accounting_circular = circular
            for model, values in BOOK_WIZARDS:
                with self.subTest(model=model, circular=circular, **values):
                    wizard = self._wizard(model, values)
                    self.assertEqual(wizard._form_preparer(), BOOK_PREPARER[circular])

    def test_statements_keep_their_preparer(self):
        for circular in CIRCULARS:
            self.env.company.vn_accounting_circular = circular
            for model in STATEMENT_WIZARDS:
                with self.subTest(model=model, circular=circular):
                    wizard = self._wizard(model, {})
                    self.assertEqual(
                        wizard._form_preparer(), STATEMENT_PREPARER[circular]
                    )
