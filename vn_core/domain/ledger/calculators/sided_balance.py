# -*- coding: utf-8 -*-
"""One-sided balance presentation.

VAS forms show "Số dư đầu kỳ" and "Số dư cuối kỳ" as a single Nợ *or* Có
figure, never as a signed number and never as a gross debit/credit pair. This
calculator performs that split once so no report repeats it.
"""

from ....core.utils.number import round_amount
from ....dto.ledger import SidedBalanceDTO


class SidedBalanceCalculator:

    @staticmethod
    def split(balance, rounding):
        """Present a net balance as Nợ / Có."""
        rounded = round_amount(balance, rounding)
        return SidedBalanceDTO(
            balance=rounded,
            debit_balance=rounded if rounded > 0 else 0.0,
            credit_balance=-rounded if rounded < 0 else 0.0,
        )
