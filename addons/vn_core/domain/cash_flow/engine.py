# -*- coding: utf-8 -*-
"""Cash Flow Engine — Báo cáo lưu chuyển tiền tệ, phương pháp trực tiếp (B03-DN).

Part 5 §16 assumed both the direct and the indirect method could be built from a
``LedgerSummaryDTO``. That is true of the indirect method and false of the
direct one: once balances are summed by account, the pairing between a cash
movement and what caused it is gone. So this engine reads journal entries rather
than balances, and asks the mapping which cash-flow item each counterpart
account belongs to.

Two pseudo-codes are injected before formulas run, so that opening and closing
cash need no extra field on the mapping::

    __opening_cash__    cash held at the start of the period
    __closing_cash__    cash held at the end

Item 60 of B03-DN is therefore just ``formula = "__opening_cash__"``.

The report checks itself: item 70 must equal the closing balance of the cash
accounts. Cash is the one figure in a financial statement that can be verified
against an independent number, and if a counterpart account is unmapped the
difference is exactly what went missing.

Pure Python: no Odoo, no SQL.
"""

from ...core.enums import GroupBy
from ...core.exceptions import MappingException, ValidationException
from ...core.utils.number import is_zero, round_amount
from ...dto.financial_statement import (
    BalanceCheckDTO, FinancialStatementDTO, FinancialStatementLineDTO,
    UnmappedAccountDTO,
)
from ..financial_statement.expression import AccountExpression
from ..financial_statement.formula import FormulaEvaluator
from .calculators.allocation import CashFlowAllocator

# Imported rather than repeated: the direct and the indirect method share one
# mapping convention, and two copies of a magic string drift.
from ..financial_statement.engine import CLOSING_CASH, OPENING_CASH  # noqa: E402

DEFAULT_CASH_EXPRESSION = '111*,112*,113*'


class CashFlowEngine:

    def __init__(self, ledger_engine, mapping_repository):
        self._ledger = ledger_engine
        self._mappings = mapping_repository

    # ==================================================================
    # Public API
    # ==================================================================
    def compute(self, ledger_filter, mapping_code, with_diagnostics=True):
        if not ledger_filter.date_from:
            raise ValidationException(
                'A cash flow statement covers a period; date_from is required.')

        mapping = self._mappings.get_mapping(mapping_code,
                                             ledger_filter.company_ids)
        if not mapping:
            raise MappingException("Mapping %r not found." % mapping_code)

        context = self._ledger._load_context(ledger_filter)
        rounding = context['currency'].rounding
        accounts = context['accounts']

        cash_ids = {a.id for a in AccountExpression.resolve(
            mapping.cash_expression or DEFAULT_CASH_EXPRESSION, accounts)}
        if not cash_ids:
            raise MappingException(
                "The cash expression %r matches no account."
                % (mapping.cash_expression or DEFAULT_CASH_EXPRESSION))

        flows = self._attribute_flows(ledger_filter, cash_ids)
        opening, closing = self._cash_position(ledger_filter, cash_ids, rounding)

        amounts = self._amounts(mapping, flows, accounts, rounding)
        amounts[OPENING_CASH] = opening
        amounts[CLOSING_CASH] = closing
        self._apply_formulas(mapping, amounts, rounding)

        lines = tuple(
            FinancialStatementLineDTO(
                code=line.code, name=line.name,
                amount=amounts.get(line.code, 0.0),
                level=line.level, sequence=line.sequence,
                parent_code=line.parent_code, note_ref=line.note_ref,
                bold=line.bold, is_computed=bool(line.formula),
            )
            for line in sorted(mapping.lines, key=lambda l: (l.sequence, l.code))
            if line.visible
        )

        unmapped, check = (), None
        if with_diagnostics:
            unmapped = self._unmapped(mapping, flows, accounts, cash_ids,
                                      rounding)
            check = self._closing_check(amounts, closing, rounding)

        return FinancialStatementDTO(
            mapping_code=mapping.code, report_name=mapping.name,
            report_type=mapping.report_type, version=mapping.version,
            company=context['companies'][0], currency=context['currency'],
            lines=lines, date_from=ledger_filter.date_from,
            date_to=ledger_filter.date_to,
            balance_check=check, unmapped=unmapped,
        )

    # ==================================================================
    # Flows
    # ==================================================================
    def _attribute_flows(self, ledger_filter, cash_ids):
        """-> ``{account_id: [signed cash amounts]}``.

        Amounts are kept individually rather than summed, because a line
        restricted to one direction — repaying a loan against drawing one, both
        on 341 — has to keep the inflows apart from the outflows.
        """
        lines = tuple(self._ledger._repo.get_move_lines(ledger_filter))
        if not lines:
            return {}

        move_ids = {line.move_id for line in lines}
        sums = self._ledger._repo.get_move_account_sums(tuple(move_ids))

        by_move = {}
        for row in sums:
            by_move.setdefault(row.move_id, []).append(row)

        flows = {}
        for move_id, rows in by_move.items():
            for account_id, amount in CashFlowAllocator.attribute(rows,
                                                                  cash_ids):
                if amount:
                    flows.setdefault(account_id, []).append(amount)
        return flows

    def _cash_position(self, ledger_filter, cash_ids, rounding):
        balances = self._ledger.compute_balances(ledger_filter, GroupBy.ACCOUNT)
        opening = sum(summary.opening for key, summary in balances.items()
                      if key[0] in cash_ids)
        closing = sum(summary.closing for key, summary in balances.items()
                      if key[0] in cash_ids)
        return round_amount(opening, rounding), round_amount(closing, rounding)

    # ==================================================================
    # Mapping
    # ==================================================================
    def _amounts(self, mapping, flows, accounts, rounding):
        amounts = {}
        for line in mapping.lines:
            if line.formula or not line.expression:
                continue
            selected = {a.id for a in
                        AccountExpression.resolve(line.expression, accounts)}
            total = 0.0
            for account_id in selected:
                for amount in flows.get(account_id, ()):
                    if CashFlowAllocator.keeps(amount, line.side):
                        total += amount
            amounts[line.code] = round_amount(total * line.sign, rounding)
        return amounts

    def _apply_formulas(self, mapping, amounts, rounding):
        formulas = {l.code: l.formula for l in mapping.lines if l.formula}
        if not formulas:
            return
        signs = {l.code: l.sign for l in mapping.lines if l.formula}
        for code in FormulaEvaluator.resolution_order(formulas):
            value = FormulaEvaluator.evaluate(formulas[code], amounts)
            amounts[code] = round_amount(value * signs.get(code, 1), rounding)

    # ==================================================================
    # Diagnostics
    # ==================================================================
    def _unmapped(self, mapping, flows, accounts, cash_ids, rounding):
        """Counterpart accounts that moved cash but no item claims.

        On a cash flow statement this matters more than anywhere else: an
        unmapped counterpart does not merely omit a line, it makes the whole
        statement fail to reconcile to the bank.
        """
        covered = set()
        for line in mapping.lines:
            if line.expression:
                covered |= {a.id for a in
                            AccountExpression.resolve(line.expression, accounts)}

        by_id = {a.id: a for a in accounts}
        missing = []
        for account_id, amounts in flows.items():
            if account_id in covered or account_id in cash_ids:
                continue
            total = round_amount(sum(amounts), rounding)
            if is_zero(total, rounding):
                continue
            account = by_id.get(account_id)
            if account is None:
                continue
            missing.append(UnmappedAccountDTO(
                id=account.id, code=account.code, name=account.name,
                balance=total))
        return tuple(sorted(missing, key=lambda a: a.code))

    def _closing_check(self, amounts, closing, rounding):
        """Item 70 against the actual closing balance of the cash accounts."""
        reported = round_amount(amounts.get('70', 0.0), rounding)
        difference = round_amount(reported - closing, rounding)
        return BalanceCheckDTO(
            left_code='70', right_code='Số dư tiền cuối kỳ',
            left_amount=reported, right_amount=closing,
            difference=difference,
            is_balanced=is_zero(difference, rounding),
        )
