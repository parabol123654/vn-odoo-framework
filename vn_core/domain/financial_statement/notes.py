# -*- coding: utf-8 -*-
"""Figures for the numeric tables of the notes to the financial statements.

The notes (B09-DNN under TT133) are mostly text the company writes. Their
tables, though, restate and break down the balance sheet and the income
statement, and a table that disagrees with the statement it explains is worse
than no table. So the figures are read the way the statements read them: each
row is turned into a statement line and handed to the Financial Statement
Engine, which already knows sides, signs, partners and the year-end transfer.

Three kinds of table, matching the columns the forms print:

``balance``
    Closing balance; comparative is the balance the day before the year
    starts ("Cuối năm / Đầu năm", B09-DNN V.1–V.4).
``period``
    The year's movement; comparative is the previous year's ("Năm nay / Năm
    trước", VI.1–VI.9). The year-end transfer is left out, as on B02.
``movement``
    Opening, increase, decrease, closing (V.5 fixed assets, V.10 taxes, V.13
    equity). The increase is the movement on the side that grows the row —
    debit for an asset (``sign`` 1), credit for a liability or equity
    (``sign`` -1) — and the decrease the other side, so that opening +
    increase − decrease = closing always holds.

The comparative computed here is a fallback. The circular takes it from last
year's notes (TT133 Điều 81 mục 2.5.5, 2.5.6), not from the ledger; the caller
decides which to use.

Pure Python: no Odoo, no database.
"""

from datetime import timedelta

from ...core.exceptions import MappingException
from ...core.utils.number import round_amount
from ...dto.financial_statement import MappingDTO, MappingLineDTO
from ...dto.notes import NoteRowValueDTO
from .formula import FormulaEvaluator

LAYOUT_BALANCE = 'balance'
LAYOUT_PERIOD = 'period'
LAYOUT_MOVEMENT = 'movement'
LAYOUTS = (LAYOUT_BALANCE, LAYOUT_PERIOD, LAYOUT_MOVEMENT)

SCOPE_RELATED = 'related'

FIGURE_CLOSING = 'closing'
FIGURE_OPENING = 'opening'
FIGURE_NET = 'net'
FIGURES = (FIGURE_CLOSING, FIGURE_OPENING, FIGURE_NET, 'debit', 'credit')


class NotesCalculator:

    def __init__(self, statement_engine):
        self._engine = statement_engine

    # ==================================================================
    # Public API
    # ==================================================================
    def compute(self, table, ledger_filter, previous_filter=None):
        """-> ``{row_code: NoteRowValueDTO}`` for the rows read from the ledger.

        ``ledger_filter`` spans the financial year. ``previous_filter`` spans
        the year before; only a 'period' table needs it, for its fallback
        comparative. Rows filled in by hand and formula rows are left out:
        formulas must also total the hand-filled rows, so they are applied
        afterwards with ``apply_formulas``.
        """
        self._validate(table)
        rows = tuple(r for r in table.rows if r.expression)
        if not rows:
            return {}
        values = {}
        for scope in sorted({r.partner_scope for r in rows}):
            group = tuple(r for r in rows if r.partner_scope == scope)
            year, previous = ledger_filter, previous_filter
            if scope == SCOPE_RELATED:
                if not table.related_partner_ids:
                    # No partner is marked as a related party: nothing to
                    # read, and certainly not the whole account.
                    values.update({r.code: NoteRowValueDTO(
                        r.code, 0.0, 0.0,
                        0.0 if table.layout == LAYOUT_MOVEMENT else None,
                        0.0 if table.layout == LAYOUT_MOVEMENT else None)
                        for r in group})
                    continue
                ids = tuple(table.related_partner_ids)
                year = ledger_filter.replace(partner_ids=ids)
                if previous is not None:
                    previous = previous.replace(partner_ids=ids)
            if table.layout == LAYOUT_MOVEMENT:
                values.update(self._balances(table, group, year))
            else:
                values.update(self._figures(table, group, year, previous))
        return values

    @classmethod
    def apply_formulas(cls, table, values, rounding=None):
        """Fill the formula rows of ``table`` from ``values``.

        ``values`` maps row codes to ``NoteRowValueDTO`` (ledger rows and
        hand-filled rows alike); the result adds one entry per formula row.
        Increase and decrease are not totalled blindly: in "Giá trị còn lại =
        Nguyên giá − Hao mòn", depreciation is an increase of the accumulated
        depreciation and a decrease of the carrying amount. A term that enters
        a formula with a minus sign therefore contributes its increase to the
        total's decrease and the other way round.
        """
        formulas = {r.code: r.formula for r in table.rows if r.formula}
        if not formulas:
            return dict(values)
        result = dict(values)
        for code in FormulaEvaluator.resolution_order(formulas):
            formula = formulas[code]
            coefficients = cls._coefficients(formula)
            current = cls._evaluate(formula, result, 'current', rounding)
            opening = cls._evaluate(formula, result, 'opening', rounding)
            increase = decrease = None
            if table.layout == LAYOUT_MOVEMENT:
                increase = decrease = 0.0
                for term, coefficient in coefficients.items():
                    row = result.get(term)
                    if row is None:
                        continue
                    up, down = row.increase or 0.0, row.decrease or 0.0
                    if coefficient < 0:
                        up, down = down, up
                    increase += abs(coefficient) * up
                    decrease += abs(coefficient) * down
                increase = round_amount(increase, rounding)
                decrease = round_amount(decrease, rounding)
            result[code] = NoteRowValueDTO(
                code=code, current=current, opening=opening,
                increase=increase, decrease=decrease)
        return result

    # ==================================================================
    # Ledger reads
    # ==================================================================
    def _balances(self, table, rows, ledger_filter):
        """Opening, increase, decrease and closing of a 'movement' table."""
        if ledger_filter.date_from is None:
            raise MappingException(
                "Table %r needs the first day of the year." % table.code)
        mapping = self._mapping(table, rows, basis='closing')
        closing = self._engine.amounts_for(
            ledger_filter.replace(date_from=None), mapping)
        opening = self._engine.amounts_for(
            self._day_before(ledger_filter), mapping)
        debit = self._engine.amounts_for(
            ledger_filter, self._mapping(table, rows, 'movement', 'debit'))
        credit = self._engine.amounts_for(
            ledger_filter, self._mapping(table, rows, 'movement', 'credit'))

        values = {}
        for row in rows:
            # Both reads used sign 1: debits come back positive, credits
            # negative (see FinancialStatementEngine._value).
            debits = debit.get(row.code, 0.0)
            credits = -credit.get(row.code, 0.0)
            increase, decrease = ((debits, credits) if row.sign >= 0
                                  else (credits, debits))
            values[row.code] = NoteRowValueDTO(
                code=row.code,
                current=closing.get(row.code, 0.0),
                opening=opening.get(row.code, 0.0),
                increase=increase, decrease=decrease)
        return values

    def _figures(self, table, rows, ledger_filter, previous_filter):
        """Rows of a 'balance' or 'period' table, each by its own figure.

        ``opening`` is what the comparative column falls back to: for a
        balance, the same balance a year earlier; for a movement, the
        previous year's movement.
        """
        if ledger_filter.date_from is None:
            raise MappingException(
                "Table %r needs the first day of the year." % table.code)
        default = FIGURE_CLOSING if table.layout == LAYOUT_BALANCE \
            else FIGURE_NET
        groups = {}
        for row in rows:
            groups.setdefault(row.figure or default, []).append(row)

        values = {}
        for figure, group in groups.items():
            group = tuple(group)
            if figure in (FIGURE_CLOSING, FIGURE_OPENING):
                mapping = self._mapping(table, group, basis='closing')
                if figure == FIGURE_CLOSING:
                    current_filter = ledger_filter.replace(date_from=None)
                    earlier_filter = self._day_before(ledger_filter)
                else:
                    current_filter = self._day_before(ledger_filter)
                    earlier_filter = (self._day_before(previous_filter)
                                      if previous_filter is not None
                                      else None)
            else:
                side = None if figure == FIGURE_NET else figure
                mapping = self._mapping(table, group, 'movement', side,
                                        keep_sign=True)
                current_filter, earlier_filter = ledger_filter, previous_filter
            current = self._engine.amounts_for(current_filter, mapping)
            earlier = (self._engine.amounts_for(earlier_filter, mapping)
                       if earlier_filter is not None else None)
            for row in group:
                values[row.code] = NoteRowValueDTO(
                    code=row.code,
                    current=current.get(row.code, 0.0),
                    opening=(earlier.get(row.code, 0.0)
                             if earlier is not None else None))
        return values

    @staticmethod
    def _day_before(ledger_filter):
        """As-at filter for the day before ``ledger_filter``'s year."""
        return ledger_filter.replace(
            date_from=None,
            date_to=ledger_filter.date_from - timedelta(days=1))

    @staticmethod
    def _mapping(table, rows, basis, movement_side=None, keep_sign=False):
        """A one-off statement mapping made of the table's ledger rows.

        For the two one-sided reads of a 'movement' table the sign is forced
        to 1 and the side to 'both': the caller assigns debit and credit to
        increase and decrease itself, by the row's sign. A row that asks for
        one side of the movement as its figure (``keep_sign``) keeps both.
        """
        lines = []
        for sequence, row in enumerate(rows):
            one_sided = movement_side is not None and not keep_sign
            lines.append(MappingLineDTO(
                code=row.code, name=row.code, sequence=sequence,
                expression=row.expression,
                sign=1 if one_sided else row.sign,
                side='both' if one_sided else row.side,
                split_by_partner=row.split_by_partner,
                movement_side=movement_side or row.movement_side,
                maturity=row.maturity))
        return MappingDTO(
            code='notes:%s' % table.code, name=table.code,
            report_type='notes', basis=basis,
            overdue_days=table.overdue_days,
            # The year-end transfer is left out of every movement a row
            # reads, as on B02, but not out of a 'movement' table: there the
            # transfer of the year's profit to 421 is a real increase.
            closing_expression=(table.closing_expression
                                if basis == 'movement'
                                and table.layout != LAYOUT_MOVEMENT else ''),
            lines=tuple(lines))

    # ==================================================================
    # Formulas
    # ==================================================================
    @staticmethod
    def _coefficients(formula):
        """``{code: coefficient}`` of a linear formula such as ``a + b - c``.

        Found by evaluating the formula with one code set to 1 and the rest
        to 0; the grammar has only +, - and parentheses, so every formula is
        linear and this is exact.
        """
        return {
            code: FormulaEvaluator.evaluate(formula, {code: 1.0})
            for code in FormulaEvaluator.referenced_codes(formula)
        }

    @staticmethod
    def _evaluate(formula, values, column, rounding):
        amounts = {}
        for code, row in values.items():
            value = getattr(row, column)
            if value is not None:
                amounts[code] = value
        if column == 'opening' and not amounts:
            return None
        return round_amount(FormulaEvaluator.evaluate(formula, amounts),
                            rounding)

    # ==================================================================
    # Validation
    # ==================================================================
    @staticmethod
    def _validate(table):
        if table.layout not in LAYOUTS:
            raise MappingException(
                "Table %r has an unknown layout %r." % (table.code,
                                                        table.layout))
        seen = set()
        for row in table.rows:
            if row.code in seen:
                raise MappingException(
                    "Duplicate row code %r in table %r." % (row.code,
                                                            table.code))
            seen.add(row.code)
            if row.expression and row.formula:
                raise MappingException(
                    "Row %r has both an expression and a formula; it must "
                    "have one or the other." % row.code)
            if row.partner_scope not in ('', SCOPE_RELATED):
                raise MappingException(
                    "Row %r has an unknown partner scope %r."
                    % (row.code, row.partner_scope))
            if row.figure and row.figure not in FIGURES:
                raise MappingException(
                    "Row %r has an unknown figure %r." % (row.code,
                                                          row.figure))
        FormulaEvaluator.resolution_order(
            {r.code: r.formula for r in table.rows if r.formula})
