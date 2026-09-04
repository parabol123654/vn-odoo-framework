# -*- coding: utf-8 -*-
"""Account expression parser and resolver (Part 9 §7, §15, §16).

An expression selects accounts by code, never by database id, so a mapping
survives a re-installed or customised chart::

    111                  exactly account 111
    111*                 every account whose code starts with 111
    111*,112*            cash plus bank
    111*,-1113           all of 111 except the 1113 sub-tree
    111*,112*,-1113      combinations of the above

Exclusions are applied after inclusions regardless of where they appear, so
order inside the expression never changes the result.

Deliberately *not* part of the syntax: debit/credit restriction and per-partner
splitting. Those are fields on the mapping line instead. Encoding them in the
string would mean a parser change every time a new dimension appears, and they
are properties of how a figure is measured rather than of which accounts it
covers.

Pure Python: no Odoo, no database.
"""

from ...core.exceptions import MappingException

WILDCARD = '*'
EXCLUDE = '-'


class AccountExpression:

    @staticmethod
    def parse(expression):
        """-> ``(includes, excludes)``, each a tuple of code patterns.

        Raises ``MappingException`` on an empty or malformed token so a typo in
        a mapping surfaces at once instead of silently producing a zero line.
        """
        includes, excludes = [], []
        if not expression or not expression.strip():
            return (), ()

        for raw in expression.split(','):
            token = raw.strip()
            if not token:
                continue
            target = includes
            if token.startswith(EXCLUDE):
                target = excludes
                token = token[1:].strip()
            if not token:
                raise MappingException(
                    "Empty term in account expression %r." % expression)
            if WILDCARD in token[:-1]:
                raise MappingException(
                    "'%s' is invalid: a wildcard may only end a pattern." % token)
            target.append(token)
        return tuple(includes), tuple(excludes)

    @staticmethod
    def matches(code, pattern):
        if pattern.endswith(WILDCARD):
            return code.startswith(pattern[:-1])
        return code == pattern

    @classmethod
    def resolve(cls, expression, accounts):
        """-> tuple of ``AccountDTO`` selected by ``expression``.

        ``accounts`` is the chart in scope. An expression that matches nothing
        is allowed: a company may genuinely not use account 121, and the line
        should print zero rather than abort the whole statement.
        """
        includes, excludes = cls.parse(expression)
        if not includes:
            return ()

        selected = [
            account for account in accounts
            if any(cls.matches(account.code, p) for p in includes)
            and not any(cls.matches(account.code, p) for p in excludes)
        ]
        return tuple(sorted(selected, key=lambda a: a.code))
