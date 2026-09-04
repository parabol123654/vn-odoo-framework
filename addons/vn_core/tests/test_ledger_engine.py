# -*- coding: utf-8 -*-
"""Ledger Engine tests against the in-memory repository.

Not a single line of Odoo is involved: this is the payoff of keeping the Domain
pure. The whole opening-balance / running-balance / counterpart behaviour is
verified in milliseconds without a database.
"""

import unittest
from datetime import date

from ..core.enums import GroupBy, TargetMove
from ..core.exceptions import BusinessException, ValidationException
from ..domain.ledger.engine import LedgerEngine
from ..dto.common import AccountDTO, CompanyDTO, CurrencyDTO, PartnerDTO
from ..dto.filters import LedgerFilter
from ..dto.ledger import MoveLineDTO
from .fakes import FakeLedgerRepository

VND = CurrencyDTO(id=1, name='VND', rounding=1.0, decimal_places=0)
USD = CurrencyDTO(id=2, name='USD', rounding=0.01, decimal_places=2)

ACME = CompanyDTO(id=1, name='ACME Furniture', currency=VND)

RECEIVABLE = AccountDTO(131, '131', 'Phải thu khách hàng',
                        include_initial_balance=True)
REVENUE = AccountDTO(511, '511', 'Doanh thu bán hàng',
                     include_initial_balance=False)
VAT_OUT = AccountDTO(3331, '3331', 'Thuế GTGT phải nộp',
                     include_initial_balance=True)
ACCOUNTS = (RECEIVABLE, REVENUE, VAT_OUT)

PARTNERS = (PartnerDTO(7, 'Công ty Nội thất Hoa Mai'),
            PartnerDTO(8, 'Công ty Gỗ Việt'))


def _pair(move_id, when, amount, partner_id=7, state='posted', line_base=None):
    """A two-line sales entry: debit 131, credit 511."""
    base = line_base if line_base is not None else move_id * 10
    return (
        MoveLineDTO(id=base + 1, date=when, account_id=131, journal_id=1,
                    move_id=move_id, move_name='INV/%s' % move_id,
                    debit=amount, credit=0.0, balance=amount,
                    partner_id=partner_id, company_id=1, state=state,
                    label='Bán hàng'),
        MoveLineDTO(id=base + 2, date=when, account_id=511, journal_id=1,
                    move_id=move_id, move_name='INV/%s' % move_id,
                    debit=0.0, credit=amount, balance=-amount,
                    partner_id=partner_id, company_id=1, state=state,
                    label='Bán hàng'),
    )


class LedgerEngineCase(unittest.TestCase):

    lines = ()
    companies = (ACME,)

    def setUp(self):
        self.repo = FakeLedgerRepository(
            companies=self.companies, accounts=ACCOUNTS, lines=self.lines,
            partners=PARTNERS)
        self.engine = LedgerEngine(self.repo)

    def _filter(self, date_from, date_to, **kwargs):
        return LedgerFilter(date_to=date_to, date_from=date_from,
                            company_ids=(1,), **kwargs)

    def _row(self, trial_balance, account_id):
        return next(r for r in trial_balance.rows if r.account_id == account_id)

    def _group(self, ledger, key):
        return next(g for g in ledger.groups if g.key == key)


class TestOpeningBalance(LedgerEngineCase):

    lines = (_pair(1, date(2025, 6, 15), 1000.0)
             + _pair(2, date(2026, 1, 20), 300.0)
             + _pair(3, date(2026, 4, 10), 500.0))

    def test_balance_sheet_account_accumulates_across_years(self):
        result = self.engine.compute_trial_balance(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)))
        receivable = self._row(result, 131)
        self.assertEqual(receivable.opening.debit_balance, 1000.0)
        self.assertEqual(receivable.movement.debit, 800.0)
        self.assertEqual(receivable.closing.debit_balance, 1800.0)

    def test_pl_account_has_no_prior_year_opening(self):
        result = self.engine.compute_trial_balance(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)))
        revenue = self._row(result, 511)
        self.assertEqual(revenue.opening.balance, 0.0)
        self.assertEqual(revenue.closing.credit_balance, 800.0)

    def test_pl_opening_holds_current_year_only(self):
        """From 1 March, revenue opens with January–February, not 2025."""
        result = self.engine.compute_trial_balance(
            self._filter(date(2026, 3, 1), date(2026, 12, 31)))
        revenue = self._row(result, 511)
        self.assertEqual(revenue.opening.credit_balance, 300.0)
        receivable = self._row(result, 131)
        self.assertEqual(receivable.opening.debit_balance, 1300.0)

    def test_from_inception_has_no_opening_query(self):
        self.engine.compute_trial_balance(
            self._filter(None, date(2026, 12, 31)))
        # One aggregate call for the period, none for the opening.
        self.assertEqual(len(self.repo.aggregate_calls), 1)

    def test_opening_costs_two_queries_not_one_per_account(self):
        self.engine.compute_trial_balance(
            self._filter(date(2026, 3, 1), date(2026, 12, 31)))
        # Balance-sheet window + P&L window + the period itself.
        self.assertEqual(len(self.repo.aggregate_calls), 3)


class TestTrialBalance(LedgerEngineCase):

    lines = _pair(1, date(2026, 1, 20), 300.0) + _pair(2, date(2026, 2, 5), 500.0)

    def test_balances_within_one_fiscal_year(self):
        result = self.engine.compute_trial_balance(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)))
        self.assertTrue(result.is_balanced)
        self.assertEqual(result.total_movement.debit, 800.0)
        self.assertEqual(result.total_movement.credit, 800.0)

    def test_empty_accounts_are_omitted_by_default(self):
        result = self.engine.compute_trial_balance(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)))
        self.assertNotIn(3331, [r.account_id for r in result.rows])

    def test_empty_accounts_can_be_included(self):
        result = self.engine.compute_trial_balance(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)),
            include_empty=True)
        self.assertIn(3331, [r.account_id for r in result.rows])

    def test_rows_are_ordered_by_account_code(self):
        result = self.engine.compute_trial_balance(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)),
            include_empty=True)
        self.assertEqual([r.code for r in result.rows], ['131', '3331', '511'])


class TestUnclosedPriorYear(LedgerEngineCase):
    """A documented, correct imbalance.

    When the prior year's P&L has not been closed out to 421, a period starting
    on 1 January cannot balance: the receivable carries 2025 forward while
    revenue resets. The engine reports that rather than hiding it, because the
    accountant needs to see the missing closing entry.
    """

    lines = _pair(1, date(2025, 6, 15), 1000.0)

    def test_imbalance_is_reported(self):
        result = self.engine.compute_trial_balance(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)))
        self.assertFalse(result.is_balanced)


class TestLedgerDetail(LedgerEngineCase):

    lines = (_pair(1, date(2025, 12, 1), 200.0)
             + _pair(2, date(2026, 1, 5), 100.0)
             + _pair(3, date(2026, 1, 6), 50.0))

    def test_running_balance_starts_from_opening(self):
        ledger = self.engine.compute_ledger(
            self._filter(date(2026, 1, 1), date(2026, 1, 31),
                         account_ids=(131,)))
        group = self._group(ledger, (131,))
        self.assertEqual(group.opening.debit_balance, 200.0)
        self.assertEqual([l.running_balance for l in group.lines],
                         [300.0, 350.0])
        self.assertEqual(group.closing.debit_balance, 350.0)

    def test_group_carries_account_code_and_name(self):
        ledger = self.engine.compute_ledger(
            self._filter(date(2026, 1, 1), date(2026, 1, 31),
                         account_ids=(131,)))
        group = self._group(ledger, (131,))
        self.assertEqual(group.code, '131')
        self.assertEqual(group.display_name, '131 - Phải thu khách hàng')

    def test_counterpart_label(self):
        ledger = self.engine.compute_ledger(
            self._filter(date(2026, 1, 1), date(2026, 1, 31),
                         account_ids=(131,)),
            with_counterpart=True)
        line = self._group(ledger, (131,)).lines[0]
        self.assertEqual(line.counterpart_account_ids, (511,))
        self.assertEqual(line.counterpart_label, '511')

    def test_counterpart_is_skipped_when_not_requested(self):
        ledger = self.engine.compute_ledger(
            self._filter(date(2026, 1, 1), date(2026, 1, 31),
                         account_ids=(131,)),
            with_counterpart=False)
        self.assertEqual(
            self._group(ledger, (131,)).lines[0].counterpart_account_ids, ())

    def test_partner_grouping_resolves_names(self):
        ledger = self.engine.compute_ledger(
            self._filter(date(2026, 1, 1), date(2026, 1, 31),
                         account_ids=(131,)),
            group_by=GroupBy.PARTNER)
        group = self._group(ledger, (7,))
        self.assertEqual(group.name, 'Công ty Nội thất Hoa Mai')

    def test_lines_carry_their_own_account(self):
        """Sổ Nhật ký chung is ungrouped, so each line must name its account."""
        journal = self.engine.compute_journal(
            self._filter(date(2026, 1, 1), date(2026, 1, 31)))
        codes = {line.account_code for line in journal.groups[0].lines}
        self.assertEqual(codes, {'131', '511'})
        line = journal.groups[0].lines[0]
        self.assertEqual(line.account_label, '131 - Phải thu khách hàng')

    def test_journal_keeps_chronological_order_and_no_grouping(self):
        journal = self.engine.compute_journal(
            self._filter(date(2026, 1, 1), date(2026, 1, 31)))
        self.assertEqual(len(journal.groups), 1)
        lines = journal.groups[0].lines
        self.assertEqual([l.date for l in lines],
                         [date(2026, 1, 5), date(2026, 1, 5),
                          date(2026, 1, 6), date(2026, 1, 6)])
        self.assertTrue(all(l.running_balance == 0.0 for l in lines))


class TestCounterpartOutsideFilter(unittest.TestCase):
    """The bug a partner ledger made visible.

    Database ids are deliberately unlike the account codes here, exactly as they
    are in a real chart. Restricting the report to 131 leaves 511 out of the
    catalogue the report loaded, and without resolving it separately the
    counterpart column printed "78" where the accountant expected "511".
    """

    RECEIVABLE = AccountDTO(41, '131', 'Phải thu của khách hàng',
                            include_initial_balance=True)
    REVENUE = AccountDTO(78, '511', 'Doanh thu bán hàng',
                         include_initial_balance=False)
    VAT = AccountDTO(143, '3331', 'Thuế GTGT phải nộp',
                     include_initial_balance=True)

    def setUp(self):
        lines = (
            MoveLineDTO(id=1, date=date(2026, 3, 10), account_id=41,
                        journal_id=1, move_id=1, move_name='INV/1',
                        debit=1100.0, credit=0.0, balance=1100.0,
                        partner_id=7, company_id=1, label='Bán hàng'),
            MoveLineDTO(id=2, date=date(2026, 3, 10), account_id=78,
                        journal_id=1, move_id=1, move_name='INV/1',
                        debit=0.0, credit=1000.0, balance=-1000.0,
                        partner_id=7, company_id=1, label='Bán hàng'),
            MoveLineDTO(id=3, date=date(2026, 3, 10), account_id=143,
                        journal_id=1, move_id=1, move_name='INV/1',
                        debit=0.0, credit=100.0, balance=-100.0,
                        partner_id=7, company_id=1, label='Bán hàng'),
        )
        self.repo = FakeLedgerRepository(
            companies=(ACME,),
            accounts=(self.RECEIVABLE, self.REVENUE, self.VAT),
            lines=lines, partners=PARTNERS)
        self.engine = LedgerEngine(self.repo)

    def _report(self):
        return self.engine.compute_ledger(
            LedgerFilter(date_from=date(2026, 1, 1), date_to=date(2026, 12, 31),
                         company_ids=(1,), account_ids=(41,)),
            with_counterpart=True)

    def test_counterparts_show_codes_not_database_ids(self):
        line = self._report().groups[0].lines[0]
        self.assertEqual(line.counterpart_label, '511, 3331')

    def test_the_raw_ids_do_not_appear(self):
        label = self._report().groups[0].lines[0].counterpart_label
        for account in (self.REVENUE, self.VAT):
            self.assertNotIn(str(account.id), label)

    def test_the_reported_account_itself_is_still_named(self):
        line = self._report().groups[0].lines[0]
        self.assertEqual(line.account_code, '131')


class TestExpenseLedger(unittest.TestCase):
    """Sổ chi phí sản xuất, kinh doanh (S36-DN).

    Account 154 over March 2026: an opening carried from December, materials
    (152), labour (334), one entry whose counterparts span two roots, and a
    closing transfer to 155. The breakdown must equal the "TK đối ứng" column
    read sideways — same source, no allocation invented.
    """

    WIP = AccountDTO(54, '154', 'Chi phí SXKD dở dang',
                     include_initial_balance=True)
    MATERIALS = AccountDTO(52, '152', 'Nguyên liệu, vật liệu',
                           include_initial_balance=True)
    TOOLS = AccountDTO(53, '153', 'Công cụ, dụng cụ',
                       include_initial_balance=True)
    WAGES = AccountDTO(34, '334', 'Phải trả người lao động',
                       include_initial_balance=True)
    GOODS = AccountDTO(55, '155', 'Thành phẩm',
                       include_initial_balance=True)

    @staticmethod
    def _entry(move_id, when, debits, credits, base):
        lines, position = [], 0
        for account_id, amount in debits:
            lines.append(MoveLineDTO(
                id=base + position, date=when, account_id=account_id,
                journal_id=1, move_id=move_id, move_name='KT/%s' % move_id,
                debit=amount, credit=0.0, balance=amount, company_id=1,
                label='Bút toán %s' % move_id))
            position += 1
        for account_id, amount in credits:
            lines.append(MoveLineDTO(
                id=base + position, date=when, account_id=account_id,
                journal_id=1, move_id=move_id, move_name='KT/%s' % move_id,
                debit=0.0, credit=amount, balance=-amount, company_id=1,
                label='Bút toán %s' % move_id))
            position += 1
        return tuple(lines)

    def setUp(self):
        lines = (
            # December 2025: opening WIP the new year carries forward.
            self._entry(1, date(2025, 12, 20), [(54, 400.0)], [(52, 400.0)], 10)
            # March 2026: materials, labour, one multi-root issue, transfer.
            + self._entry(11, date(2026, 3, 5), [(54, 600.0)], [(52, 600.0)], 110)
            + self._entry(12, date(2026, 3, 12), [(54, 300.0)], [(34, 300.0)], 120)
            + self._entry(13, date(2026, 3, 18), [(54, 200.0)],
                          [(52, 120.0), (53, 80.0)], 130)
            + self._entry(14, date(2026, 3, 31), [(55, 700.0)], [(54, 700.0)], 140)
        )
        self.repo = FakeLedgerRepository(
            companies=(ACME,),
            accounts=(self.WIP, self.MATERIALS, self.TOOLS, self.WAGES,
                      self.GOODS),
            lines=lines, partners=PARTNERS)
        self.engine = LedgerEngine(self.repo)

    def _report(self, **kwargs):
        return self.engine.compute_expense_ledger(
            LedgerFilter(date_from=date(2026, 3, 1), date_to=date(2026, 3, 31),
                         company_ids=(1,), account_ids=(54,)),
            **kwargs)

    def test_columns_are_counterpart_roots_plus_residual(self):
        group = self._report().groups[0]
        self.assertEqual(group.columns, ('152', '334', ''))

    def test_each_debit_lands_whole_in_its_column(self):
        group = self._report().groups[0]
        materials = next(l for l in group.lines if l.move_name == 'KT/11')
        self.assertEqual(materials.amounts, (600.0, 0.0, 0.0))
        wages = next(l for l in group.lines if l.move_name == 'KT/12')
        self.assertEqual(wages.amounts, (0.0, 300.0, 0.0))

    def test_multi_root_line_is_not_split_by_guesswork(self):
        group = self._report().groups[0]
        mixed = next(l for l in group.lines if l.move_name == 'KT/13')
        self.assertEqual(mixed.amounts, (0.0, 0.0, 200.0))
        self.assertEqual(mixed.counterpart_label, '152, 153')

    def test_credit_side_is_one_figure_not_detail_rows(self):
        group = self._report().groups[0]
        self.assertEqual(group.credit_total, 700.0)
        self.assertEqual(len(group.lines), 3)

    def test_breakdown_cross_foots_to_the_debit_total(self):
        group = self._report().groups[0]
        self.assertEqual(group.column_totals, (600.0, 300.0, 200.0))
        self.assertEqual(sum(group.column_totals), group.debit_total)

    def test_opening_carries_and_closing_follows(self):
        group = self._report().groups[0]
        self.assertEqual(group.opening.debit_balance, 400.0)
        self.assertEqual(group.closing.debit_balance, 800.0)

    def test_breakdown_limit_folds_the_tail_into_the_residual(self):
        group = self._report(breakdown_limit=1).groups[0]
        self.assertEqual(group.columns, ('152', ''))
        self.assertEqual(group.column_totals, (600.0, 500.0))


class TestSalesLedger(unittest.TestCase):
    """Sổ chi tiết bán hàng (S35-DN).

    Two invoiced products, one credit note, one hand-written revenue entry
    with no product, and the year-end transfer to 911 — which must never look
    like a sale.
    """

    from ..dto.inventory import ProductDTO as _P
    BAN_AN = _P(1, 'TP001', 'Bộ bàn ăn gỗ sồi', 'Bộ')
    GHE = _P(2, 'TP002', 'Ghế văn phòng', 'Cái')

    ACCOUNTS = (
        AccountDTO(31, '131', 'Phải thu của khách hàng'),
        AccountDTO(51, '511', 'Doanh thu bán hàng',
                   include_initial_balance=False),
        AccountDTO(52, '5211', 'Chiết khấu thương mại',
                   include_initial_balance=False),
        AccountDTO(33, '3331', 'Thuế GTGT phải nộp'),
        AccountDTO(91, '911', 'Xác định kết quả kinh doanh',
                   include_initial_balance=False),
    )

    @staticmethod
    def _line(line_id, move_id, account_id, when, debit=0.0, credit=0.0,
              product_id=None, quantity=0.0, label=''):
        return MoveLineDTO(
            id=line_id, date=when, account_id=account_id, journal_id=1,
            move_id=move_id, move_name='BH/%s' % move_id, debit=debit,
            credit=credit, balance=debit - credit, company_id=1,
            product_id=product_id, quantity=quantity, label=label)

    def setUp(self):
        when = date(2026, 3, 10)
        lines = (
            # Invoice: two tables at 150 each plus VAT.
            self._line(1, 1, 31, when, debit=330.0),
            self._line(2, 1, 51, when, credit=300.0,
                       product_id=1, quantity=2.0, label='Bàn ăn'),
            self._line(3, 1, 33, when, credit=30.0),
            # Invoice: one chair.
            self._line(4, 2, 31, when, debit=110.0),
            self._line(5, 2, 51, when, credit=100.0,
                       product_id=2, quantity=1.0, label='Ghế'),
            self._line(6, 2, 33, when, credit=10.0),
            # Credit note: trade discount on the tables.
            self._line(7, 3, 52, when, debit=50.0,
                       product_id=1, quantity=0.0, label='Chiết khấu'),
            self._line(8, 3, 33, when, debit=5.0),
            self._line(9, 3, 31, when, credit=55.0),
            # Hand-written revenue with no product.
            self._line(10, 4, 51, when, credit=40.0, label='Doanh thu khác'),
            self._line(11, 4, 31, when, debit=40.0),
            # Year-end transfer: not a sale.
            self._line(12, 5, 51, date(2026, 12, 31), debit=440.0),
            self._line(13, 5, 91, date(2026, 12, 31), credit=440.0),
        )
        self.repo = FakeLedgerRepository(
            companies=(ACME,), accounts=self.ACCOUNTS, lines=lines,
            partners=PARTNERS, products=(self.BAN_AN, self.GHE))
        self.engine = LedgerEngine(self.repo)

    def _report(self, **kw):
        return self.engine.compute_sales_ledger(
            LedgerFilter(date_from=date(2026, 1, 1), date_to=date(2026, 12, 31),
                         company_ids=(1,), account_ids=(51, 52), **kw))

    def _group(self, report, product_id):
        return next(g for g in report.groups
                    if (g.product.id if g.product else None) == product_id)

    def test_revenue_and_deductions_meet_on_the_product(self):
        group = self._group(self._report(), 1)
        self.assertEqual(group.revenue_total, 300.0)
        self.assertEqual(group.deduction_total, 50.0)
        self.assertEqual(group.net_revenue, 250.0)
        self.assertEqual(group.quantity_total, 2.0)

    def test_unit_price_is_what_the_ledger_saw(self):
        group = self._group(self._report(), 1)
        revenue_line = next(l for l in group.lines if l.revenue)
        self.assertEqual(revenue_line.unit_price, 150.0)

    def test_the_closing_transfer_is_not_a_sale(self):
        report = self._report()
        self.assertEqual(report.total_revenue, 440.0)
        self.assertNotIn(
            'BH/5',
            [l.move_name for g in report.groups for l in g.lines])

    def test_productless_revenue_is_grouped_last_not_dropped(self):
        report = self._report()
        self.assertIsNone(report.groups[-1].product)
        self.assertEqual(report.groups[-1].revenue_total, 40.0)

    def test_the_book_still_adds_up_to_the_revenue_account(self):
        report = self._report()
        self.assertEqual(report.total_net_revenue, 440.0 - 50.0)

    def test_product_filter_narrows_the_book(self):
        report = self._report(product_ids=(1,))
        self.assertEqual([g.product.id for g in report.groups], [1])


class TestAllocationTable(unittest.TestCase):
    """Bảng phân bổ NVL, CCDC (07-VT).

    March 2026: materials to production and overheads, tools to overheads, a
    prepaid amortisation to administration, one issue whose debit side spans
    two roots, one return to store, and a December issue that must stay out.
    """

    ACCOUNTS = (
        AccountDTO(52, '152', 'Nguyên liệu, vật liệu'),
        AccountDTO(53, '153', 'Công cụ, dụng cụ'),
        AccountDTO(42, '242', 'Chi phí trả trước'),
        AccountDTO(21, '621', 'Chi phí NVL trực tiếp',
                   include_initial_balance=False),
        AccountDTO(27, '627', 'Chi phí sản xuất chung',
                   include_initial_balance=False),
        AccountDTO(62, '642', 'Chi phí quản lý kinh doanh',
                   include_initial_balance=False),
    )

    _entry = staticmethod(TestExpenseLedger._entry)

    def setUp(self):
        lines = (
            # December: out of period.
            self._entry(1, date(2025, 12, 10), [(21, 999.0)], [(52, 999.0)], 10)
            # March.
            + self._entry(11, date(2026, 3, 3), [(21, 500.0)], [(52, 500.0)], 110)
            + self._entry(12, date(2026, 3, 8), [(27, 200.0)], [(52, 200.0)], 120)
            + self._entry(13, date(2026, 3, 12), [(27, 90.0)], [(53, 90.0)], 130)
            + self._entry(14, date(2026, 3, 20), [(62, 60.0)], [(42, 60.0)], 140)
            # Debit side spans 621 and 627: residual row, whole.
            + self._entry(15, date(2026, 3, 25), [(21, 70.0), (27, 30.0)],
                          [(52, 100.0)], 150)
            # A return to store: debit 152, must not net the issues down.
            + self._entry(16, date(2026, 3, 28), [(52, 40.0)], [(21, 40.0)], 160)
        )
        self.repo = FakeLedgerRepository(
            companies=(ACME,), accounts=self.ACCOUNTS, lines=lines,
            partners=PARTNERS)
        self.engine = LedgerEngine(self.repo)

    def _report(self):
        return self.engine.compute_allocation_table(
            LedgerFilter(date_from=date(2026, 3, 1), date_to=date(2026, 3, 31),
                         company_ids=(1,), account_ids=(52, 53, 42)))

    def _row(self, report, code):
        return next(r for r in report.rows if r.code == code)

    def test_columns_are_the_credited_roots(self):
        self.assertEqual(self._report().columns, ('152', '153', '242'))

    def test_cells_cross_tab_debit_root_against_credited_account(self):
        report = self._report()
        self.assertEqual(self._row(report, '621').amounts, (500.0, 0.0, 0.0))
        self.assertEqual(self._row(report, '627').amounts, (200.0, 90.0, 0.0))
        self.assertEqual(self._row(report, '642').amounts, (0.0, 0.0, 60.0))

    def test_multi_root_issue_lands_whole_on_the_residual_row(self):
        report = self._report()
        self.assertEqual(self._row(report, '').amounts, (100.0, 0.0, 0.0))
        self.assertEqual(report.rows[-1].code, '')

    def test_returns_are_not_netted_off(self):
        """The form reports what was issued; a return is a receipt."""
        self.assertEqual(self._row(self._report(), '621').total, 500.0)

    def test_out_of_period_issues_stay_out(self):
        self.assertEqual(self._report().grand_total, 950.0)

    def test_column_totals_reconcile_to_the_credit_side(self):
        report = self._report()
        self.assertEqual(report.column_totals, (800.0, 90.0, 60.0))
        self.assertEqual(report.grand_total, sum(report.column_totals))


class TestVoucherNumber(LedgerEngineCase):
    """Sổ quỹ prints the voucher number, not the journal entry name.

    S07-DN asks for the number on the Phiếu thu or Phiếu chi. An entry that is
    not a cash voucher has none, and falls back to the entry name rather than
    printing a blank column.
    """

    lines = (
        MoveLineDTO(id=1, date=date(2026, 3, 5), account_id=131, journal_id=1,
                    move_id=1, move_name='MISC/2026/03/0001', debit=100.0,
                    credit=0.0, balance=100.0, company_id=1,
                    voucher_number='PT/2026/00001'),
        MoveLineDTO(id=2, date=date(2026, 3, 6), account_id=131, journal_id=1,
                    move_id=2, move_name='MISC/2026/03/0002', debit=50.0,
                    credit=0.0, balance=50.0, company_id=1),
    )

    def test_voucher_number_wins_when_present(self):
        ledger = self.engine.compute_ledger(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)))
        self.assertEqual(self._group(ledger, (131,)).lines[0].move_name,
                         'PT/2026/00001')

    def test_entry_name_is_used_when_there_is_no_voucher(self):
        ledger = self.engine.compute_ledger(
            self._filter(date(2026, 1, 1), date(2026, 12, 31)))
        self.assertEqual(self._group(ledger, (131,)).lines[1].move_name,
                         'MISC/2026/03/0002')


class TestDraftHandling(LedgerEngineCase):

    lines = (_pair(1, date(2026, 1, 5), 100.0)
             + _pair(2, date(2026, 1, 6), 700.0, state='draft'))

    def test_posted_only_excludes_draft(self):
        result = self.engine.compute_trial_balance(
            self._filter(date(2026, 1, 1), date(2026, 1, 31)))
        self.assertEqual(self._row(result, 131).movement.debit, 100.0)

    def test_all_entries_includes_draft(self):
        result = self.engine.compute_trial_balance(
            self._filter(date(2026, 1, 1), date(2026, 1, 31),
                         target_move=TargetMove.ALL))
        self.assertEqual(self._row(result, 131).movement.debit, 800.0)


class TestResidualAtDate(LedgerEngineCase):

    lines = _pair(1, date(2026, 1, 5), 1000.0)

    def setUp(self):
        super().setUp()
        # 400 of the invoice was matched in March, after our reporting date.
        self.repo.reconciled_after = {11: 400.0}

    def test_reconciliations_after_the_date_are_added_back(self):
        residual = self.engine.compute_residual_at_date(
            self._filter(None, date(2026, 1, 31)))
        self.assertEqual(residual[11], 400.0)


class TestValidation(LedgerEngineCase):

    def test_missing_company_is_rejected(self):
        bad = LedgerFilter(date_to=date(2026, 1, 31), company_ids=())
        with self.assertRaises(ValidationException):
            self.engine.compute_trial_balance(bad)

    def test_reversed_dates_are_rejected(self):
        with self.assertRaises(ValidationException):
            self.engine.compute_trial_balance(
                self._filter(date(2026, 3, 1), date(2026, 1, 1)))

    def test_mixed_currency_companies_are_rejected(self):
        repo = FakeLedgerRepository(
            companies=(ACME, CompanyDTO(id=2, name='US Sub', currency=USD)),
            accounts=ACCOUNTS, lines=())
        engine = LedgerEngine(repo)
        with self.assertRaises(BusinessException):
            engine.compute_trial_balance(
                LedgerFilter(date_to=date(2026, 1, 31), company_ids=(1, 2)))


if __name__ == '__main__':
    unittest.main()
