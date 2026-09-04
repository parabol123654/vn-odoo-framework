# -*- coding: utf-8 -*-
"""Aged receivable / payable calculator (Part 4 §1 — Customer/Vendor Aging).

Two rules live here and nowhere else.

**Which items are open.** An item counts when its residual *as at the reporting
date* is non-zero on the side being reported. The residual has to be
reconstructed for that date — ``amount_residual`` on the record is a today
figure — but that reconstruction belongs to the Engine, which owns the
repository. This calculator receives the residuals already corrected.

**Which column an item falls into.** Age is measured in days from either the
due date or the document date, and the buckets are half-open on the lower side
so no item can land in two columns or in none.

No database access, no Odoo import.
"""

from ....core.enums import AgingSide
from ....core.utils.number import is_zero
from ....dto.ledger import AgingBucketDTO

#: The columns a Vietnamese aged-balance form normally carries.
DEFAULT_BUCKETS = (
    AgingBucketDTO('Trong hạn', None, None),
    AgingBucketDTO('Quá hạn 1-30 ngày', 1, 30),
    AgingBucketDTO('Quá hạn 31-60 ngày', 31, 60),
    AgingBucketDTO('Quá hạn 61-90 ngày', 61, 90),
    AgingBucketDTO('Quá hạn 91-180 ngày', 91, 180),
    AgingBucketDTO('Quá hạn trên 180 ngày', 181, None),
)


class AgingCalculator:

    @staticmethod
    def days_overdue(line, as_of, basis_due_date=True):
        """Positive when overdue, zero or negative when not yet due."""
        reference = (line.date_maturity or line.date) if basis_due_date else line.date
        return (as_of - reference).days

    @staticmethod
    def bucket_index(days, buckets):
        """Index of the column ``days`` belongs to.

        The not-yet-due column absorbs everything with ``days <= 0``. Overdue
        columns are matched on their inclusive bounds, and the final open-ended
        bucket catches whatever is older than the last upper bound, so an item
        can never fall through.
        """
        if days <= 0:
            for index, bucket in enumerate(buckets):
                if bucket.is_current:
                    return index
            return 0

        for index, bucket in enumerate(buckets):
            if bucket.is_current:
                continue
            if bucket.upper is None:
                if days >= bucket.lower:
                    return index
            elif bucket.lower <= days <= bucket.upper:
                return index

        # Older than every declared bucket: fall into the last one rather than
        # silently dropping the amount out of the report.
        return len(buckets) - 1

    @staticmethod
    def keeps(residual, side, rounding):
        """Whether an item belongs on the receivable or the payable report.

        A residual is positive on a debit balance. Receivable reports keep the
        debit side, payable reports the credit side; an item that has flipped
        sign — a customer in credit, say — is therefore reported on the other
        form rather than shown as a negative here.
        """
        if is_zero(residual, rounding):
            return False
        return residual > 0 if side is AgingSide.RECEIVABLE else residual < 0

    @staticmethod
    def sign(side):
        """Payables are presented as positive amounts on their own form."""
        return 1.0 if side is AgingSide.RECEIVABLE else -1.0
