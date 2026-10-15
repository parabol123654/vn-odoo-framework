# -*- coding: utf-8 -*-
"""Financial Statement Engine.

Turns a mapping plus ledger balances into the lines of a statutory form. It
never reads ``account.move.line``: the Ledger Engine supplies balances, and this
layer only maps, signs, splits and totals them.

Execution order::

    mapping -> expression -> account balances -> side split -> sign
            -> formula (in dependency order) -> DTO

Three things here are worth knowing about, because getting any of them wrong
produces a statement that looks plausible and is wrong.

**The side split is per partner.** On a Vietnamese balance sheet, account 131
feeds two different items: "Phải thu ngắn hạn của khách hàng" takes the debit
side, "Người mua trả tiền trước" the credit side. Both are computed customer by
customer and then summed. Netting the account first — the obvious
implementation — cancels a customer who owes against a customer who has prepaid,
and both items come out too small.

**Sign is data, not code.** Revenue accounts carry credit balances, so the P&L
line for revenue maps 511 with ``sign = -1``. No account code appears in Python.

**Basis differs by statement.** A balance sheet reads closing balances, a P&L
reads the period's movement. That is a property of the mapping, not of the
engine.

Pure Python: no Odoo, no database.
"""

from ...core.enums import GroupBy
from ...core.exceptions import MappingException
from ...core.utils.number import round_amount
from ...core.utils.number import is_zero
from ...dto.financial_statement import (
    BalanceCheckDTO, FinancialStatementDTO, FinancialStatementLineDTO,
    UnmappedAccountDTO,
)
from .expression import AccountExpression

#: Pseudo-codes a cash flow mapping can name in a formula. Kept identical to the
#: direct engine's so one mapping convention covers both methods.
OPENING_CASH = '__opening_cash__'
CLOSING_CASH = '__closing_cash__'
from .formula import FormulaEvaluator

TERM_ALL = 'all'
TERM_SHORT = 'short'
TERM_LONG = 'long'

MOVEMENT_NET = 'net'
MOVEMENT_DEBIT = 'debit'
MOVEMENT_CREDIT = 'credit'

SIDE_BOTH = 'both'
SIDE_DEBIT = 'debit_only'
SIDE_CREDIT = 'credit_only'

BASIS_CLOSING = 'closing'
BASIS_MOVEMENT = 'movement'


class FinancialStatementEngine:

    def __init__(self, ledger_engine, mapping_repository):
        self._ledger = ledger_engine
        self._mappings = mapping_repository

    # ==================================================================
    # Public API
    # ==================================================================
    def compute(self, ledger_filter, mapping_code, comparative_filter=None,
                with_diagnostics=True):
        """Build one statement.

        ``comparative_filter`` produces the "Số đầu năm" / prior-period column
        that every Vietnamese statutory form carries, by running the same
        mapping over a second period.
        """
        mapping = self._mappings.get_mapping(mapping_code,
                                             ledger_filter.company_ids)
        if not mapping:
            raise MappingException("Mapping %r not found." % mapping_code)
        self._validate(mapping)

        amounts = self._amounts(ledger_filter, mapping)
        previous = (self._amounts(comparative_filter, mapping)
                    if comparative_filter else None)
        line_accounts = self._line_accounts(
            mapping, self._ledger._repo.get_accounts(ledger_filter))

        context = self._ledger._load_context(ledger_filter)
        lines = tuple(
            FinancialStatementLineDTO(
                code=line.code,
                name=line.name,
                amount=amounts.get(line.code, 0.0),
                previous_amount=(previous.get(line.code, 0.0)
                                 if previous is not None else None),
                level=line.level,
                sequence=line.sequence,
                parent_code=line.parent_code,
                note_ref=line.note_ref,
                bold=line.bold,
                is_computed=bool(line.formula),
                account_ids=line_accounts.get(line.code, ()),
            )
            for line in sorted(mapping.lines, key=lambda l: (l.sequence, l.code))
            if line.visible
        )
        diagnostics = ((), None)
        if with_diagnostics:
            diagnostics = self._diagnose(ledger_filter, mapping, amounts,
                                         context['currency'].rounding)

        return FinancialStatementDTO(
            mapping_code=mapping.code,
            report_name=mapping.name,
            report_type=mapping.report_type,
            version=mapping.version,
            company=context['companies'][0],
            currency=context['currency'],
            lines=lines,
            date_from=ledger_filter.date_from,
            date_to=ledger_filter.date_to,
            comparative=previous is not None,
            unmapped=diagnostics[0],
            balance_check=diagnostics[1],
        )

    def amounts_for(self, ledger_filter, mapping):
        """-> ``{line_code: amount}`` for a mapping built by the caller.

        ``compute`` loads its mapping by code from the repository. The notes
        to the financial statements (B09) build theirs from the note's own
        table rows instead, and read the same balances the same way.
        """
        self._validate(mapping)
        return self._amounts(ledger_filter, mapping)

    # ==================================================================
    # Diagnostics
    # ==================================================================
    def _diagnose(self, ledger_filter, mapping, amounts, rounding):
        """What the mapping failed to cover, and whether the form balances.

        This exists because the alternative is worse. A statutory mapping has
        around ninety items; whoever fills it in will miss some, and a balance
        sheet with a missing account prints happily and is wrong. Reporting the
        gap turns a silent error into a list of account codes to fix.
        """
        return (self._unmapped_accounts(ledger_filter, mapping, rounding),
                self._balance_check(mapping, amounts, rounding))

    def _unmapped_accounts(self, ledger_filter, mapping, rounding):
        accounts = self._ledger._repo.get_accounts(ledger_filter)
        ledger_filter = self._measured_filter(ledger_filter, mapping, accounts)
        covered = set()
        for line in mapping.lines:
            if line.expression:
                covered |= {a.id for a in
                            AccountExpression.resolve(line.expression, accounts)}

        balances = self._ledger.compute_balances(ledger_filter, GroupBy.ACCOUNT)
        by_id = {a.id: a for a in accounts}

        missing = []
        for key, summary in balances.items():
            account_id = key[0]
            if account_id in covered:
                continue
            value = self._value(summary, mapping.basis)
            if is_zero(value, rounding):
                continue
            account = by_id.get(account_id)
            if account is None:
                continue
            missing.append(UnmappedAccountDTO(
                id=account.id, code=account.code, name=account.name,
                balance=round_amount(value, rounding)))
        return tuple(sorted(missing, key=lambda a: a.code))

    @staticmethod
    def _check_label(code):
        """Pseudo-codes are machinery; a reader should see what they mean."""
        return {
            OPENING_CASH: 'Số dư tiền đầu kỳ',
            CLOSING_CASH: 'Số dư tiền cuối kỳ',
        }.get(code, code)

    def _balance_check(self, mapping, amounts, rounding):
        """Evaluate the mapping's own equality, e.g. "270=440"."""
        if not mapping.balance_check:
            return None
        parts = mapping.balance_check.split('=')
        if len(parts) != 2:
            raise MappingException(
                "Balance check %r must be of the form '270=440'."
                % mapping.balance_check)
        left, right = (p.strip() for p in parts)
        left_amount = round_amount(amounts.get(left, 0.0), rounding)
        right_amount = round_amount(amounts.get(right, 0.0), rounding)
        difference = round_amount(left_amount - right_amount, rounding)
        return BalanceCheckDTO(
            left_code=self._check_label(left),
            right_code=self._check_label(right),
            left_amount=left_amount, right_amount=right_amount,
            difference=difference,
            is_balanced=is_zero(difference, rounding),
        )

    # ==================================================================
    # Which accounts a line is made of
    # ==================================================================
    def _line_accounts(self, mapping, accounts):
        """-> ``{line_code: (account_id, ...)}``, transitive through formulas.

        This is what makes an item on a statement openable. Item 100 has no
        expression of its own — it is ``110 + 120 + 130`` — so its accounts are
        the union of what those three resolve to, and so on down. Walking the
        formulas in dependency order means a parent is always computed after its
        children, using the same ordering that computes the amounts.
        """
        resolved = {}
        for line in mapping.lines:
            if line.expression:
                resolved[line.code] = tuple(sorted(
                    a.id for a in
                    AccountExpression.resolve(line.expression, accounts)))

        formulas = {l.code: l.formula for l in mapping.lines if l.formula}
        for code in FormulaEvaluator.resolution_order(formulas):
            ids = set()
            for reference in FormulaEvaluator.referenced_codes(formulas[code]):
                ids |= set(resolved.get(reference, ()))
            resolved[code] = tuple(sorted(ids))
        return resolved

    # ==================================================================
    # Amounts
    # ==================================================================
    def _amounts(self, ledger_filter, mapping):
        rounding = self._ledger._load_context(ledger_filter)['currency'].rounding
        accounts = self._ledger._repo.get_accounts(ledger_filter)
        measured = self._measured_filter(ledger_filter, mapping, accounts)

        by_account = self._ledger.compute_balances(measured, GroupBy.ACCOUNT)
        by_account_partner = None
        if any(l.split_by_partner for l in mapping.lines):
            by_account_partner = self._ledger.compute_balances(
                measured, GroupBy.ACCOUNT_PARTNER)
        by_term = None
        if any(l.maturity in (TERM_SHORT, TERM_LONG) for l in mapping.lines):
            by_term = self._ledger.compute_balances(
                measured.replace(
                    long_term_after=self._one_year_after(measured.date_to)),
                GroupBy.ACCOUNT_PARTNER_TERM)

        amounts = {}
        for line in mapping.lines:
            if line.formula or not line.expression:
                continue
            selected = AccountExpression.resolve(line.expression, accounts)
            if line.maturity in (TERM_SHORT, TERM_LONG):
                value = self._sum_by_term(line, selected, mapping.basis,
                                          by_term)
            else:
                value = self._sum(line, selected, mapping.basis,
                                  by_account, by_account_partner)
            amounts[line.code] = round_amount(value * line.sign, rounding)

        self._inject_cash_position(ledger_filter, mapping, accounts, amounts,
                                   rounding)
        self._apply_formulas(mapping, amounts, rounding)
        return amounts

    def _inject_cash_position(self, ledger_filter, mapping, accounts, amounts,
                              rounding):
        """Opening and closing cash, for a statement that needs them.

        Only the cash flow statement does, and only when the mapping says which
        accounts are cash. The indirect method needs the same two figures the
        direct one does — the period's opening and closing cash — and gets them
        the same way, through pseudo-codes a formula can name:

            60  formula = __opening_cash__
            70  formula = 50 + 60 + 61   with balance_check 70=__closing_cash__

        That last line is what makes the indirect statement self-verifying. An
        indirect cash flow is a chain of adjustments to profit, and a single
        wrong sign anywhere in it produces a total that still looks plausible;
        checking it against the actual cash balance is the only way to know.
        """
        if not mapping.cash_expression:
            return
        cash_ids = {a.id for a in
                    AccountExpression.resolve(mapping.cash_expression, accounts)}
        if not cash_ids:
            raise MappingException(
                "The cash expression %r matches no account."
                % mapping.cash_expression)

        balances = self._ledger.compute_balances(ledger_filter, GroupBy.ACCOUNT)
        amounts[OPENING_CASH] = round_amount(
            sum(summary.opening for key, summary in balances.items()
                if key[0] in cash_ids), rounding)
        amounts[CLOSING_CASH] = round_amount(
            sum(summary.closing for key, summary in balances.items()
                if key[0] in cash_ids), rounding)

    @staticmethod
    def _measured_filter(ledger_filter, mapping, accounts):
        """The filter the mapping's figures are read with.

        A statement of the period's movement leaves out the year-end transfer.
        A closing entry moves revenue and expense to 911 (or straight to 421);
        it is not itself revenue or expense, and reading the net movement with
        it included gives zero on every income statement line. The accounts are
        mapping data, so a company that closes elsewhere changes data, not code.
        """
        if mapping.basis != BASIS_MOVEMENT or not mapping.closing_expression:
            return ledger_filter
        closing_ids = tuple(sorted(
            a.id for a in
            AccountExpression.resolve(mapping.closing_expression, accounts)))
        if not closing_ids:
            return ledger_filter
        return ledger_filter.replace(exclude_move_account_ids=closing_ids)

    @staticmethod
    def _one_year_after(day):
        """Twelve months on, the boundary of short term (Điều 73 khoản 4)."""
        try:
            return day.replace(year=day.year + 1)
        except ValueError:              # 29 February
            return day.replace(year=day.year + 1, day=28)

    def _sum(self, line, accounts, basis, by_account, by_account_partner):
        if not accounts:
            return 0.0
        account_ids = {a.id for a in accounts}

        if line.split_by_partner:
            # Evaluate the side customer by customer, then add up. See the
            # module docstring for why netting first would be wrong.
            total = 0.0
            for key, summary in (by_account_partner or {}).items():
                if key[0] in account_ids:
                    total += self._sided(
                        self._value(summary, basis, line.movement_side),
                        line.side)
            return total

        total = 0.0
        for account_id in account_ids:
            summary = by_account.get((account_id,))
            if summary is not None:
                total += self._sided(
                    self._value(summary, basis, line.movement_side), line.side)
        return total

    def _sum_by_term(self, line, accounts, basis, by_term):
        """Short- or long-term part of a balance, account by account.

        Each (account, partner) balance is split by the due dates of its
        items. A payment reduces the short-term part first: it settles what
        falls due soonest, so the long-term part is the long-dated items
        capped at what is still owed, and the short-term part is the rest.
        """
        if not accounts:
            return 0.0
        account_ids = {a.id for a in accounts}
        parts = {}
        for (account_id, partner_id, long_term), summary in (
                by_term or {}).items():
            if account_id not in account_ids:
                continue
            short, long_ = parts.get((account_id, partner_id), (0.0, 0.0))
            value = self._value(summary, basis, line.movement_side)
            if long_term:
                long_ += value
            else:
                short += value
            parts[(account_id, partner_id)] = (short, long_)

        wanted = {}
        for (account_id, partner_id), (short, long_) in parts.items():
            net = short + long_
            if net > 0:
                long_part = min(max(long_, 0.0), net)
            elif net < 0:
                long_part = max(min(long_, 0.0), net)
            else:
                long_part = 0.0
            part = long_part if line.maturity == TERM_LONG else net - long_part
            key = (account_id, partner_id) if line.split_by_partner \
                else (account_id,)
            wanted[key] = wanted.get(key, 0.0) + part
        return sum(self._sided(value, line.side) for value in wanted.values())

    @staticmethod
    def _value(summary, basis, movement_side=MOVEMENT_NET):
        if basis == BASIS_MOVEMENT:
            if movement_side == MOVEMENT_DEBIT:
                return summary.movement.debit
            if movement_side == MOVEMENT_CREDIT:
                # Credits read as a negative balance, as everywhere else, so
                # a revenue line keeps its usual sign of -1.
                return -summary.movement.credit
            return summary.movement.balance
        return summary.closing

    @staticmethod
    def _sided(value, side):
        if side == SIDE_DEBIT:
            return value if value > 0 else 0.0
        if side == SIDE_CREDIT:
            return value if value < 0 else 0.0
        return value

    def _apply_formulas(self, mapping, amounts, rounding):
        formulas = {l.code: l.formula for l in mapping.lines if l.formula}
        if not formulas:
            return
        signs = {l.code: l.sign for l in mapping.lines if l.formula}
        for code in FormulaEvaluator.resolution_order(formulas):
            value = FormulaEvaluator.evaluate(formulas[code], amounts)
            amounts[code] = round_amount(value * signs.get(code, 1), rounding)

    # ==================================================================
    # Validation
    # ==================================================================
    def _validate(self, mapping):
        seen = set()
        for line in mapping.lines:
            if line.code in seen:
                raise MappingException(
                    "Duplicate line code %r in mapping %r."
                    % (line.code, mapping.code))
            seen.add(line.code)
            if line.expression and line.formula:
                raise MappingException(
                    "Line %r has both an expression and a formula; it must "
                    "have one or the other." % line.code)
            if line.side not in (SIDE_BOTH, SIDE_DEBIT, SIDE_CREDIT):
                raise MappingException(
                    "Line %r has an unknown side %r." % (line.code, line.side))
            if line.movement_side not in (MOVEMENT_NET, MOVEMENT_DEBIT,
                                          MOVEMENT_CREDIT):
                raise MappingException(
                    "Line %r has an unknown movement side %r."
                    % (line.code, line.movement_side))
            if line.maturity not in (TERM_ALL, TERM_SHORT, TERM_LONG):
                raise MappingException(
                    "Line %r has an unknown maturity %r."
                    % (line.code, line.maturity))

        for line in mapping.lines:
            if line.parent_code and line.parent_code not in seen:
                raise MappingException(
                    "Line %r refers to a missing parent %r."
                    % (line.code, line.parent_code))
            if line.expression:
                AccountExpression.parse(line.expression)

        formulas = {l.code: l.formula for l in mapping.lines if l.formula}
        FormulaEvaluator.resolution_order(formulas)

        if mapping.basis not in (BASIS_CLOSING, BASIS_MOVEMENT):
            raise MappingException(
                "Mapping %r has an unknown basis %r."
                % (mapping.code, mapping.basis))
