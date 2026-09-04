# -*- coding: utf-8 -*-
"""Attributing a cash movement to the accounts that caused it.

Part 17 §4.3 recorded this as an open architectural problem: a journal entry
with several lines has several counterpart accounts, and the cash amount looked
like it would need an arbitrary allocation rule. Writing it out showed the
assumption was wrong.

A journal entry balances. So in any entry that touches cash, the non-cash side
**is** the cash flow, account by account, with the sign flipped::

    Nợ 111   1,100      cash in  1,100
    Có 511   1,000  ->  attributable to 511:  1,000
    Có 3331    100  ->  attributable to 3331:   100
                                              -----
                                               1,100

No proportional split, no approximation, and the parts always add back to the
cash movement because the entry balanced in the first place. A transfer between
two cash accounts nets to zero and correctly produces no flow at all; a transfer
carrying a bank charge produces exactly the charge.

The only judgement left is which accounts count as cash, and that is mapping
data rather than code.
"""


class CashFlowAllocator:

    @staticmethod
    def attribute(move_sums, cash_account_ids):
        """-> ``[(account_id, cash_amount)]`` for one journal entry.

        ``move_sums`` are the per-account totals of a single entry. Returns
        nothing at all when the entry never touches cash, and nothing when the
        cash lines net to zero, which is what an internal transfer should do.
        """
        cash_movement = 0.0
        attributed = []
        for row in move_sums:
            balance = row.debit - row.credit
            if row.account_id in cash_account_ids:
                cash_movement += balance
            else:
                # Flipping the sign turns "what the other side did" into "what
                # happened to cash because of it".
                attributed.append((row.account_id, -balance))

        if not cash_movement and not any(amount for _, amount in attributed):
            return ()
        if not any(row.account_id in cash_account_ids for row in move_sums):
            return ()
        return tuple(attributed)

    @staticmethod
    def keeps(amount, side):
        """Whether a flow belongs to a line restricted to one direction.

        Borrowing and repaying a loan both post to 341; what tells them apart is
        the direction of the cash, so the mapping's ``side`` is read here as
        inflow or outflow rather than as a debit or credit balance.
        """
        if side == 'debit_only':
            return amount > 0
        if side == 'credit_only':
            return amount < 0
        return True
