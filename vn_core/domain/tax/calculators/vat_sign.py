# -*- coding: utf-8 -*-
"""VAT sign normalisation.

Output VAT sits on the credit side of 3331 and input VAT on the debit side of
133, so the raw ledger balances carry opposite signs. A filing wants both listed
as positive amounts, with credit notes negative.

Normalising by direction rather than by account code keeps the rule true for any
chart of accounts::

    sale     -> tax_amount = -balance
    purchase -> tax_amount = +balance

A credit note reverses the entry, so it comes out negative on its own without a
special case — which is what the filing expects, since a refund reduces the
period's declared output or input VAT.
"""

from ....core.enums import TaxDirection


class VatSignCalculator:

    @staticmethod
    def factor(direction):
        return -1.0 if direction is TaxDirection.SALE else 1.0

    @classmethod
    def normalise(cls, amount, direction):
        return amount * cls.factor(direction)
