# -*- coding: utf-8 -*-
"""Financial statement domain tests. No Odoo, no database."""

import unittest
from datetime import date

from ..core.exceptions import MappingException
from ..domain.financial_statement.engine import FinancialStatementEngine
from ..domain.financial_statement.expression import AccountExpression
from ..domain.financial_statement.formula import FormulaEvaluator
from ..domain.financial_statement.repository import IMappingRepository
from ..domain.ledger.engine import LedgerEngine
from ..dto.common import AccountDTO, CompanyDTO, CurrencyDTO, PartnerDTO
from ..dto.filters import LedgerFilter
from ..dto.financial_statement import MappingDTO, MappingLineDTO
from ..dto.ledger import MoveLineDTO
from .fakes import FakeLedgerRepository

VND = CurrencyDTO(id=1, name='VND', rounding=1.0, decimal_places=0)
ACME = CompanyDTO(id=1, name='ACME Furniture', currency=VND)


def _account(id_, code, name, bs=True):
    return AccountDTO(id_, code, name, include_initial_balance=bs)


CHART = (
    _account(1, '1111', 'Tiền mặt'),
    _account(2, '1121', 'Tiền gửi ngân hàng'),
    _account(3, '1131', 'Tiền đang chuyển'),
    _account(4, '131', 'Phải thu của khách hàng'),
    _account(5, '331', 'Phải trả cho người bán'),
    _account(6, '511', 'Doanh thu bán hàng', bs=False),
    _account(7, '521', 'Các khoản giảm trừ', bs=False),
    _account(8, '632', 'Giá vốn hàng bán', bs=False),
    _account(9, '642', 'Chi phí quản lý', bs=False),
)


class FakeMappingRepository(IMappingRepository):

    def __init__(self, mappings):
        self._mappings = {m.code: m for m in mappings}

    def get_mapping(self, code, company_ids):
        return self._mappings.get(code)

    def list_mappings(self, report_type=None, company_ids=None):
        return tuple(self._mappings.values())


# ======================================================================
# Expression
# ======================================================================
class TestExpression(unittest.TestCase):

    def _codes(self, expression):
        return [a.code for a in AccountExpression.resolve(expression, CHART)]

    def test_exact_code(self):
        self.assertEqual(self._codes('131'), ['131'])

    def test_wildcard(self):
        self.assertEqual(self._codes('11*'), ['1111', '1121', '1131'])

    def test_list(self):
        self.assertEqual(self._codes('1111,1121'), ['1111', '1121'])

    def test_exclusion(self):
        self.assertEqual(self._codes('11*,-1131'), ['1111', '1121'])

    def test_exclusion_order_does_not_matter(self):
        self.assertEqual(self._codes('-1131,11*'), self._codes('11*,-1131'))

    def test_unmatched_expression_is_allowed(self):
        """A company may simply not use an account; the line prints zero."""
        self.assertEqual(self._codes('121*'), [])

    def test_empty_expression(self):
        self.assertEqual(AccountExpression.parse(''), ((), ()))

    def test_wildcard_in_the_middle_is_rejected(self):
        with self.assertRaises(MappingException):
            AccountExpression.parse('1*1')

    def test_dangling_minus_is_rejected(self):
        with self.assertRaises(MappingException):
            AccountExpression.parse('111,-')


# ======================================================================
# Formula
# ======================================================================
class TestFormula(unittest.TestCase):

    AMOUNTS = {'01': 1000.0, '02': 100.0, '11': 600.0, '21': 50.0}

    def test_subtraction(self):
        self.assertEqual(
            FormulaEvaluator.evaluate('01 - 02', self.AMOUNTS), 900.0)

    def test_chained(self):
        self.assertEqual(
            FormulaEvaluator.evaluate('01 - 02 - 11 + 21', self.AMOUNTS), 350.0)

    def test_parentheses(self):
        self.assertEqual(
            FormulaEvaluator.evaluate('01 - (02 + 11)', self.AMOUNTS), 300.0)

    def test_leading_sign(self):
        self.assertEqual(FormulaEvaluator.evaluate('-02', self.AMOUNTS), -100.0)

    def test_missing_code_counts_as_zero(self):
        self.assertEqual(
            FormulaEvaluator.evaluate('01 - 99', self.AMOUNTS), 1000.0)

    def test_referenced_codes(self):
        self.assertEqual(FormulaEvaluator.referenced_codes('20 + 21 - 22'),
                         ('20', '21', '22'))

    def test_resolution_order_puts_dependencies_first(self):
        order = FormulaEvaluator.resolution_order(
            {'50': '30 + 40', '30': '20 - 25', '40': '31 - 32'})
        self.assertLess(order.index('30'), order.index('50'))
        self.assertLess(order.index('40'), order.index('50'))

    def test_cycle_is_reported_not_recursed(self):
        with self.assertRaises(MappingException) as caught:
            FormulaEvaluator.resolution_order({'A': 'B', 'B': 'A'})
        self.assertIn('cycle', str(caught.exception).lower())

    def test_self_reference_is_a_cycle(self):
        with self.assertRaises(MappingException):
            FormulaEvaluator.resolution_order({'A': 'A + 1'})

    def test_unbalanced_parenthesis(self):
        with self.assertRaises(MappingException):
            FormulaEvaluator.evaluate('(01 - 02', self.AMOUNTS)

    def test_formula_cannot_execute_code(self):
        """A mapping is data edited by accountants; it must never eval."""
        with self.assertRaises(MappingException):
            FormulaEvaluator.evaluate('__import__("os").system("ls")',
                                      self.AMOUNTS)


# ======================================================================
# Engine
# ======================================================================
def _line(line_id, account_id, amount, when, partner_id=None, move_id=None):
    debit = amount if amount > 0 else 0.0
    credit = -amount if amount < 0 else 0.0
    return MoveLineDTO(
        id=line_id, date=when, account_id=account_id, journal_id=1,
        move_id=move_id or line_id, move_name='JE/%s' % line_id,
        debit=debit, credit=credit, balance=amount,
        partner_id=partner_id, company_id=1)


INCOME_MAPPING = MappingDTO(
    code='pnl', name='Kết quả kinh doanh', report_type='income_statement',
    basis='movement', version='TT200',
    lines=(
        MappingLineDTO('01', 'Doanh thu bán hàng', sequence=1,
                       expression='511*', sign=-1),
        MappingLineDTO('02', 'Các khoản giảm trừ', sequence=2,
                       expression='521*', sign=1),
        MappingLineDTO('10', 'Doanh thu thuần', sequence=3, formula='01 - 02',
                       bold=True),
        MappingLineDTO('11', 'Giá vốn hàng bán', sequence=4,
                       expression='632*', sign=1),
        MappingLineDTO('20', 'Lợi nhuận gộp', sequence=5, formula='10 - 11',
                       bold=True),
        MappingLineDTO('26', 'Chi phí quản lý', sequence=6,
                       expression='642*', sign=1),
        MappingLineDTO('30', 'Lợi nhuận thuần', sequence=7, formula='20 - 26',
                       bold=True),
    ))


class TestIncomeStatement(unittest.TestCase):

    def setUp(self):
        lines = (
            _line(1, 6, -1000.0, date(2026, 3, 1)),   # 511 doanh thu
            _line(2, 7, 100.0, date(2026, 3, 1)),     # 521 giảm trừ
            _line(3, 8, 600.0, date(2026, 3, 1)),     # 632 giá vốn
            _line(4, 9, 150.0, date(2026, 3, 1)),     # 642 chi phí QL
            _line(5, 6, -400.0, date(2025, 9, 1)),    # doanh thu năm trước
        )
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART,
                                    lines=lines)
        self.engine = FinancialStatementEngine(
            LedgerEngine(repo), FakeMappingRepository([INCOME_MAPPING]))
        self.filter = LedgerFilter(date_from=date(2026, 1, 1),
                                   date_to=date(2026, 12, 31), company_ids=(1,))

    def _amount(self, report, code):
        return report.by_code(code).amount

    def test_credit_balances_are_presented_positive(self):
        """Revenue sits on the credit side; sign is mapping data, not code."""
        report = self.engine.compute(self.filter, 'pnl')
        self.assertEqual(self._amount(report, '01'), 1000.0)

    def test_formula_lines(self):
        report = self.engine.compute(self.filter, 'pnl')
        self.assertEqual(self._amount(report, '10'), 900.0)   # 1000 - 100
        self.assertEqual(self._amount(report, '20'), 300.0)   # 900 - 600
        self.assertEqual(self._amount(report, '30'), 150.0)   # 300 - 150

    def test_movement_basis_ignores_prior_year_revenue(self):
        """A P&L reads the period's movement, never a cumulative balance."""
        report = self.engine.compute(self.filter, 'pnl')
        self.assertEqual(self._amount(report, '01'), 1000.0)

    def test_comparative_column(self):
        previous = LedgerFilter(date_from=date(2025, 1, 1),
                                date_to=date(2025, 12, 31), company_ids=(1,))
        report = self.engine.compute(self.filter, 'pnl',
                                     comparative_filter=previous)
        self.assertTrue(report.comparative)
        self.assertEqual(report.by_code('01').previous_amount, 400.0)

    def test_lines_come_out_in_sequence(self):
        report = self.engine.compute(self.filter, 'pnl')
        self.assertEqual([l.code for l in report.lines],
                         ['01', '02', '10', '11', '20', '26', '30'])

    def test_unknown_mapping(self):
        with self.assertRaises(MappingException):
            self.engine.compute(self.filter, 'does_not_exist')


class TestPartnerSideSplit(unittest.TestCase):
    """The rule a Vietnamese balance sheet cannot be produced without.

    Two customers on account 131: one owes 500, the other has prepaid 200. The
    balance sheet must show 500 as a receivable and 200 as "Người mua trả tiền
    trước". Netting the account first would show 300 and 0, and both items would
    be wrong.
    """

    MAPPING = MappingDTO(
        code='bs', name='Cân đối kế toán', report_type='balance_sheet',
        basis='closing', version='TT200',
        lines=(
            MappingLineDTO('131', 'Phải thu của khách hàng', sequence=1,
                           expression='131', sign=1,
                           side='debit_only', split_by_partner=True),
            MappingLineDTO('312', 'Người mua trả tiền trước', sequence=2,
                           expression='131', sign=-1,
                           side='credit_only', split_by_partner=True),
            MappingLineDTO('999', 'Số dư ròng (đối chứng)', sequence=3,
                           expression='131', sign=1),
        ))

    def setUp(self):
        lines = (
            _line(1, 4, 500.0, date(2026, 2, 1), partner_id=7),
            _line(2, 4, -200.0, date(2026, 2, 2), partner_id=8),
        )
        repo = FakeLedgerRepository(
            companies=(ACME,), accounts=CHART, lines=lines,
            partners=(PartnerDTO(7, 'Khách A'), PartnerDTO(8, 'Khách B')))
        self.engine = FinancialStatementEngine(
            LedgerEngine(repo), FakeMappingRepository([self.MAPPING]))
        self.filter = LedgerFilter(date_from=date(2026, 1, 1),
                                   date_to=date(2026, 12, 31), company_ids=(1,))

    def test_debit_side_per_partner(self):
        report = self.engine.compute(self.filter, 'bs')
        self.assertEqual(report.by_code('131').amount, 500.0)

    def test_credit_side_per_partner(self):
        report = self.engine.compute(self.filter, 'bs')
        self.assertEqual(report.by_code('312').amount, 200.0)

    def test_netting_the_account_would_have_been_wrong(self):
        report = self.engine.compute(self.filter, 'bs')
        self.assertEqual(report.by_code('999').amount, 300.0)
        self.assertNotEqual(report.by_code('131').amount,
                            report.by_code('999').amount)


class TestDiagnostics(unittest.TestCase):
    """The safety net that makes a ninety-item mapping survivable.

    Nobody fills in a statutory balance sheet without missing something. The
    engine reports what it did not cover and whether the form balances, so a
    gap shows up as a list of account codes instead of a wrong number.
    """

    MAPPING = MappingDTO(
        code='bs', name='Cân đối kế toán', report_type='balance_sheet',
        basis='closing', version='TT200', balance_check='270=440',
        lines=(
            MappingLineDTO('111', 'Tiền', sequence=1, expression='111*,112*'),
            MappingLineDTO('270', 'TỔNG TÀI SẢN', sequence=2, formula='111'),
            MappingLineDTO('440', 'TỔNG NGUỒN VỐN', sequence=3,
                           expression='331', sign=-1),
        ))

    def _engine(self, lines):
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART,
                                    lines=lines,
                                    partners=(PartnerDTO(7, 'Khách A'),))
        return FinancialStatementEngine(
            LedgerEngine(repo), FakeMappingRepository([self.MAPPING]))

    def _filter(self):
        return LedgerFilter(date_from=date(2026, 1, 1),
                            date_to=date(2026, 12, 31), company_ids=(1,))

    def test_balanced_form(self):
        lines = (_line(1, 1, 500.0, date(2026, 2, 1)),
                 _line(2, 5, -500.0, date(2026, 2, 1)))
        report = self._engine(lines).compute(self._filter(), 'bs')
        self.assertTrue(report.balance_check.is_balanced)
        self.assertEqual(report.balance_check.left_amount, 500.0)
        self.assertEqual(report.balance_check.right_amount, 500.0)

    def test_imbalance_is_reported_with_the_difference(self):
        lines = (_line(1, 1, 500.0, date(2026, 2, 1)),
                 _line(2, 5, -300.0, date(2026, 2, 1)),
                 _line(3, 4, -200.0, date(2026, 2, 1)))
        report = self._engine(lines).compute(self._filter(), 'bs')
        self.assertFalse(report.balance_check.is_balanced)
        self.assertEqual(report.balance_check.difference, 200.0)

    def test_unmapped_account_is_listed(self):
        """131 carries a balance but no line selects it."""
        lines = (_line(1, 1, 500.0, date(2026, 2, 1)),
                 _line(2, 4, -500.0, date(2026, 2, 1)))
        report = self._engine(lines).compute(self._filter(), 'bs')
        self.assertEqual([a.code for a in report.unmapped], ['131'])
        self.assertEqual(report.unmapped[0].balance, -500.0)

    def test_accounts_with_no_balance_are_not_noise(self):
        lines = (_line(1, 1, 500.0, date(2026, 2, 1)),
                 _line(2, 5, -500.0, date(2026, 2, 1)))
        report = self._engine(lines).compute(self._filter(), 'bs')
        self.assertEqual(report.unmapped, ())

    def test_diagnostics_can_be_skipped(self):
        lines = (_line(1, 1, 500.0, date(2026, 2, 1)),
                 _line(2, 4, -500.0, date(2026, 2, 1)))
        report = self._engine(lines).compute(self._filter(), 'bs',
                                             with_diagnostics=False)
        self.assertEqual(report.unmapped, ())
        self.assertIsNone(report.balance_check)

    def test_mapping_without_a_check_reports_none(self):
        mapping = self.MAPPING._replace(balance_check='')
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART, lines=())
        engine = FinancialStatementEngine(
            LedgerEngine(repo), FakeMappingRepository([mapping]))
        report = engine.compute(self._filter(), 'bs')
        self.assertIsNone(report.balance_check)

    def test_malformed_check_is_rejected(self):
        mapping = self.MAPPING._replace(balance_check='270 and 440')
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART, lines=())
        engine = FinancialStatementEngine(
            LedgerEngine(repo), FakeMappingRepository([mapping]))
        with self.assertRaises(MappingException):
            engine.compute(self._filter(), 'bs')


class TestLineAccounts(unittest.TestCase):
    """What makes an item on a statement openable.

    A total has no expression of its own, so its accounts have to be gathered
    from the items its formula names — and from theirs, all the way down.
    """

    MAPPING = MappingDTO(
        code='m', name='m', report_type='balance_sheet', basis='closing',
        lines=(
            MappingLineDTO('111', 'Tiền', sequence=1, expression='1111,1121'),
            MappingLineDTO('131', 'Phải thu', sequence=2, expression='131'),
            MappingLineDTO('110', 'Cộng tiền', sequence=3, formula='111'),
            MappingLineDTO('100', 'TÀI SẢN NGẮN HẠN', sequence=4,
                           formula='110 + 131'),
            MappingLineDTO('999', 'Chỉ tiêu chỉ là tiêu đề', sequence=5),
        ))

    def setUp(self):
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART, lines=())
        self.engine = FinancialStatementEngine(
            LedgerEngine(repo), FakeMappingRepository([self.MAPPING]))
        self.report = self.engine.compute(
            LedgerFilter(date_from=date(2026, 1, 1), date_to=date(2026, 12, 31),
                         company_ids=(1,)), 'm')

    def _accounts(self, code):
        return self.report.by_code(code).account_ids

    def test_expression_line(self):
        self.assertEqual(self._accounts('111'), (1, 2))

    def test_formula_line_inherits_from_what_it_references(self):
        self.assertEqual(self._accounts('110'), (1, 2))

    def test_nested_total_gathers_everything_below_it(self):
        self.assertEqual(self._accounts('100'), (1, 2, 4))

    def test_heading_has_no_accounts(self):
        self.assertEqual(self._accounts('999'), ())

    def test_accounts_are_deduplicated_and_sorted(self):
        mapping = self.MAPPING._replace(lines=self.MAPPING.lines + (
            MappingLineDTO('200', 'Cộng trùng', sequence=6,
                           formula='111 + 110 + 100'),))
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART, lines=())
        engine = FinancialStatementEngine(
            LedgerEngine(repo), FakeMappingRepository([mapping]))
        report = engine.compute(
            LedgerFilter(date_from=date(2026, 1, 1), date_to=date(2026, 12, 31),
                         company_ids=(1,)), 'm')
        self.assertEqual(report.by_code('200').account_ids, (1, 2, 4))


class TestIndirectCashFlow(unittest.TestCase):
    """The indirect method needs no engine of its own.

    It starts from profit and adjusts it with balance movements, which is what
    this engine already does. All it needs is the period's opening and closing
    cash, delivered through the same pseudo-codes the direct engine uses so one
    mapping convention covers both methods.
    """

    MAPPING = MappingDTO(
        code='cf', name='Lưu chuyển gián tiếp', report_type='cash_flow',
        basis='movement', version='TT133', cash_flow_method='indirect',
        cash_expression='1111', balance_check='70=__closing_cash__',
        lines=(
            MappingLineDTO('01', 'Lợi nhuận trước thuế', sequence=1,
                           expression='511*', sign=-1),
            MappingLineDTO('09', 'Tăng giảm phải thu', sequence=2,
                           expression='131*', sign=-1),
            MappingLineDTO('20', 'Lưu chuyển thuần', sequence=3,
                           formula='01 + 09', bold=True),
            MappingLineDTO('50', 'Lưu chuyển trong kỳ', sequence=4,
                           formula='20'),
            MappingLineDTO('60', 'Tiền đầu kỳ', sequence=5,
                           formula='__opening_cash__'),
            MappingLineDTO('70', 'Tiền cuối kỳ', sequence=6,
                           formula='50 + 60', bold=True),
        ))

    def _engine(self, lines):
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART,
                                    lines=lines)
        return FinancialStatementEngine(
            LedgerEngine(repo), FakeMappingRepository([self.MAPPING]))

    def _filter(self):
        return LedgerFilter(date_from=date(2026, 1, 1),
                            date_to=date(2026, 12, 31), company_ids=(1,))

    def test_cash_position_reaches_the_formulas(self):
        """Bán chịu 500 rồi thu 500: tiền cuối kỳ 500, phải thu về 0."""
        lines = (_line(1, 4, 500.0, date(2026, 2, 1)),
                 _line(2, 6, -500.0, date(2026, 2, 1)),
                 _line(3, 1, 500.0, date(2026, 3, 1)),
                 _line(4, 4, -500.0, date(2026, 3, 1)))
        report = self._engine(lines).compute(self._filter(), 'cf')
        self.assertEqual(report.by_code('01').amount, 500.0)
        self.assertEqual(report.by_code('09').amount, 0.0)
        self.assertEqual(report.by_code('70').amount, 500.0)

    def test_the_statement_checks_itself_against_real_cash(self):
        lines = (_line(1, 4, 500.0, date(2026, 2, 1)),
                 _line(2, 6, -500.0, date(2026, 2, 1)),
                 _line(3, 1, 500.0, date(2026, 3, 1)),
                 _line(4, 4, -500.0, date(2026, 3, 1)))
        report = self._engine(lines).compute(self._filter(), 'cf')
        self.assertTrue(report.balance_check.is_balanced)
        self.assertEqual(report.balance_check.right_amount, 500.0)

    def test_a_receivable_still_outstanding_holds_cash_back(self):
        """Bán chịu mà chưa thu: lợi nhuận 500 nhưng tiền vẫn 0."""
        lines = (_line(1, 4, 500.0, date(2026, 2, 1)),
                 _line(2, 6, -500.0, date(2026, 2, 1)))
        report = self._engine(lines).compute(self._filter(), 'cf')
        self.assertEqual(report.by_code('01').amount, 500.0)
        self.assertEqual(report.by_code('09').amount, -500.0)
        self.assertEqual(report.by_code('70').amount, 0.0)
        self.assertTrue(report.balance_check.is_balanced)

    def test_a_wrong_sign_is_caught_by_the_check(self):
        """Đảo dấu chỉ tiêu 09: tổng vẫn trông hợp lý, đối chiếu thì lệch."""
        broken = self.MAPPING._replace(lines=tuple(
            line._replace(sign=1) if line.code == '09' else line
            for line in self.MAPPING.lines))
        lines = (_line(1, 4, 500.0, date(2026, 2, 1)),
                 _line(2, 6, -500.0, date(2026, 2, 1)))
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART,
                                    lines=lines)
        engine = FinancialStatementEngine(
            LedgerEngine(repo), FakeMappingRepository([broken]))
        report = engine.compute(self._filter(), 'cf')
        self.assertFalse(report.balance_check.is_balanced)
        self.assertEqual(report.balance_check.difference, 1000.0)

    def test_a_statement_without_a_cash_expression_gets_no_pseudo_codes(self):
        mapping = self.MAPPING._replace(cash_expression='', balance_check='')
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART, lines=())
        engine = FinancialStatementEngine(
            LedgerEngine(repo), FakeMappingRepository([mapping]))
        report = engine.compute(self._filter(), 'cf')
        self.assertEqual(report.by_code('60').amount, 0.0)

    def test_cash_expression_matching_nothing_is_rejected(self):
        mapping = self.MAPPING._replace(cash_expression='999*')
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART, lines=())
        engine = FinancialStatementEngine(
            LedgerEngine(repo), FakeMappingRepository([mapping]))
        with self.assertRaises(MappingException):
            engine.compute(self._filter(), 'cf')


class TestMappingValidation(unittest.TestCase):

    def _engine(self, mapping):
        repo = FakeLedgerRepository(companies=(ACME,), accounts=CHART, lines=())
        return FinancialStatementEngine(
            LedgerEngine(repo), FakeMappingRepository([mapping]))

    def _run(self, mapping):
        self._engine(mapping).compute(
            LedgerFilter(date_from=date(2026, 1, 1), date_to=date(2026, 12, 31),
                         company_ids=(1,)), mapping.code)

    def _mapping(self, lines):
        return MappingDTO(code='m', name='m', report_type='balance_sheet',
                          basis='closing', lines=lines)

    def test_duplicate_code(self):
        with self.assertRaises(MappingException):
            self._run(self._mapping((
                MappingLineDTO('10', 'a', expression='111*'),
                MappingLineDTO('10', 'b', expression='112*'))))

    def test_expression_and_formula_together(self):
        with self.assertRaises(MappingException):
            self._run(self._mapping((
                MappingLineDTO('10', 'a', expression='111*', formula='20'),)))

    def test_missing_parent(self):
        with self.assertRaises(MappingException):
            self._run(self._mapping((
                MappingLineDTO('10', 'a', expression='111*',
                               parent_code='99'),)))

    def test_unknown_side(self):
        with self.assertRaises(MappingException):
            self._run(self._mapping((
                MappingLineDTO('10', 'a', expression='111*', side='sideways'),)))

    def test_unknown_basis(self):
        mapping = MappingDTO(code='m', name='m', report_type='balance_sheet',
                             basis='guesswork',
                             lines=(MappingLineDTO('10', 'a', expression='1*'),))
        with self.assertRaises(MappingException):
            self._run(mapping)


if __name__ == '__main__':
    unittest.main()
