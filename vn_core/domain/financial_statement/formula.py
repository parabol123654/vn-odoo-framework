# -*- coding: utf-8 -*-
"""Formula evaluator (Part 5 §9-10, Part 9 §9).

A formula references other **line codes**, never accounts::

    10 - 11
    20 + 21 - 22 - 25 - 26
    30 + 40

Keeping formulas free of account codes is what lets the two layers move
independently: re-mapping which accounts feed line 11 never touches the formula
that consumes it.

The grammar is deliberately tiny — line codes, ``+``, ``-``, parentheses — and
it is evaluated by an explicit parser rather than ``eval``. A mapping is data,
often edited by an accountant through the UI, so it must never be able to
execute arbitrary Python.

Pure Python: no Odoo, no database.
"""

import re

from ...core.exceptions import MappingException

TOKEN = re.compile(r'\s*(?:(?P<code>[A-Za-z0-9_.]+)|(?P<op>[-+()]))')


class FormulaEvaluator:

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    @staticmethod
    def tokenize(formula):
        tokens, position = [], 0
        while position < len(formula):
            match = TOKEN.match(formula, position)
            if not match:
                if formula[position].isspace():
                    position += 1
                    continue
                raise MappingException(
                    "Unexpected character %r in formula %r."
                    % (formula[position], formula))
            tokens.append(match.group('code') or match.group('op'))
            position = match.end()
        if not tokens:
            raise MappingException("Formula %r is empty." % formula)
        return tokens

    @classmethod
    def referenced_codes(cls, formula):
        """Line codes a formula depends on."""
        return tuple(t for t in cls.tokenize(formula)
                     if t not in ('+', '-', '(', ')'))

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    @classmethod
    def evaluate(cls, formula, amounts):
        """Evaluate ``formula`` against ``{line_code: amount}``.

        A referenced code that is missing evaluates to zero: a company may not
        use every line of a statutory form, and the parent total must still
        compute.
        """
        tokens = cls.tokenize(formula)
        value, position = cls._expression(tokens, 0, amounts, formula)
        if position != len(tokens):
            raise MappingException(
                "Trailing %r in formula %r." % (tokens[position], formula))
        return value

    @classmethod
    def _expression(cls, tokens, position, amounts, formula):
        sign = 1.0
        if position < len(tokens) and tokens[position] in ('+', '-'):
            sign = -1.0 if tokens[position] == '-' else 1.0
            position += 1
        value, position = cls._term(tokens, position, amounts, formula)
        value *= sign

        while position < len(tokens) and tokens[position] in ('+', '-'):
            operator = tokens[position]
            operand, position = cls._term(tokens, position + 1, amounts, formula)
            value = value + operand if operator == '+' else value - operand
        return value, position

    @classmethod
    def _term(cls, tokens, position, amounts, formula):
        if position >= len(tokens):
            raise MappingException("Formula %r ends unexpectedly." % formula)
        token = tokens[position]
        if token == '(':
            value, position = cls._expression(tokens, position + 1, amounts,
                                              formula)
            if position >= len(tokens) or tokens[position] != ')':
                raise MappingException(
                    "Unbalanced parenthesis in formula %r." % formula)
            return value, position + 1
        if token in ('+', '-', ')'):
            raise MappingException(
                "Unexpected %r in formula %r." % (token, formula))
        return float(amounts.get(token, 0.0)), position + 1

    # ------------------------------------------------------------------
    # Dependency ordering
    # ------------------------------------------------------------------
    @classmethod
    def resolution_order(cls, formulas):
        """Topologically order ``{code: formula}`` so dependencies come first.

        Raises ``MappingException`` naming the cycle, because a self-referential
        mapping would otherwise recurse until the stack gives out and the error
        would point nowhere near the real problem.
        """
        order, state = [], {}

        def visit(code, trail):
            status = state.get(code)
            if status == 'done':
                return
            if status == 'visiting':
                cycle = ' -> '.join(trail[trail.index(code):] + [code])
                raise MappingException("Formula cycle detected: %s" % cycle)
            state[code] = 'visiting'
            for dependency in cls.referenced_codes(formulas[code]):
                if dependency in formulas:
                    visit(dependency, trail + [code])
            state[code] = 'done'
            order.append(code)

        for code in formulas:
            visit(code, [])
        return tuple(order)
