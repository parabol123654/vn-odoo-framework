# -*- coding: utf-8 -*-
"""Tờ khai thuế giá trị gia tăng, mẫu 01/GTGT.

Built from the two VAT listings the Tax Engine already produces, rolled into the
indicators of the statutory form.

**Why this one is code and not mapping data.** The financial statements are
driven by ``vn.report.mapping`` because their inputs are accounts, and which
accounts feed which item genuinely varies between companies and circulars. The
declaration's inputs are not accounts — they are the rate buckets of the
listings — and its arithmetic is fixed by law: item 27 is 29 + 30 + 32 for every
taxpayer in the country. Making that configurable would offer a choice nobody
has, while hiding the one thing worth checking, which is whether the arithmetic
is right. It is expressed here explicitly and tested line by line instead.

**The reconciliation is the point.** A declaration built only from invoices
misses VAT posted by hand — a journal entry crediting 3331 directly produces no
tax line, so no listing row, so no indicator. That is not hypothetical: it is
exactly what made the VAT listings come out empty against hand-written demo
entries. So the engine compares what the listings produced against the period's
movement on the input and output VAT accounts, and reports the gap.

Pure Python: no Odoo, no SQL.
"""

from ...core.enums import GroupBy, TaxDirection
from ...core.exceptions import ValidationException
from ...core.utils.number import is_zero, round_amount
from ...dto.financial_statement import (
    BalanceCheckDTO, FinancialStatementDTO, FinancialStatementLineDTO,
)
from ...dto.tax import VatDeclarationInputDTO
from ..financial_statement.expression import AccountExpression

#: Accounts the declaration reconciles against, when nothing else is configured.
DEFAULT_INPUT_VAT = '133*'
DEFAULT_OUTPUT_VAT = '3331*'

#: (code, label, level, bold) — the indicators of form 01/GTGT this engine fills.
LAYOUT = (
    ('II', 'II. HÀNG HOÁ, DỊCH VỤ MUA VÀO TRONG KỲ', 0, True),
    ('23', 'Giá trị của hàng hoá, dịch vụ mua vào', 1, False),
    ('24', 'Thuế GTGT của hàng hoá, dịch vụ mua vào', 1, False),
    ('25', 'Tổng số thuế GTGT được khấu trừ kỳ này', 1, True),
    ('III', 'III. HÀNG HOÁ, DỊCH VỤ BÁN RA TRONG KỲ', 0, True),
    ('26', 'Hàng hoá, dịch vụ bán ra không chịu thuế GTGT', 1, False),
    ('27', 'Hàng hoá, dịch vụ bán ra chịu thuế GTGT', 1, True),
    ('29', 'Hàng hoá, dịch vụ bán ra chịu thuế suất 0%', 2, False),
    ('30', 'Hàng hoá, dịch vụ bán ra chịu thuế suất 5%', 2, False),
    ('31', 'Thuế GTGT của hàng hoá, dịch vụ chịu thuế suất 5%', 2, False),
    ('32', 'Hàng hoá, dịch vụ bán ra chịu thuế suất 10%', 2, False),
    ('33', 'Thuế GTGT của hàng hoá, dịch vụ chịu thuế suất 10%', 2, False),
    ('28', 'Thuế GTGT của hàng hoá, dịch vụ bán ra', 1, True),
    ('34', 'Tổng doanh thu hàng hoá, dịch vụ bán ra', 1, True),
    ('35', 'Tổng số thuế GTGT của hàng hoá, dịch vụ bán ra', 1, True),
    ('IV', 'IV. XÁC ĐỊNH NGHĨA VỤ THUẾ GTGT PHẢI NỘP', 0, True),
    ('22', 'Thuế GTGT còn được khấu trừ kỳ trước chuyển sang', 1, False),
    ('36', 'Thuế GTGT phát sinh trong kỳ', 1, False),
    ('37', 'Điều chỉnh giảm thuế GTGT của các kỳ trước', 1, False),
    ('38', 'Điều chỉnh tăng thuế GTGT của các kỳ trước', 1, False),
    ('40a', 'Thuế GTGT phải nộp của hoạt động sản xuất kinh doanh trong kỳ',
     1, True),
    ('41', 'Thuế GTGT chưa khấu trừ hết kỳ này', 1, True),
    ('42', 'Thuế GTGT đề nghị hoàn', 1, False),
    ('43', 'Thuế GTGT còn được khấu trừ chuyển kỳ sau', 1, True),
)

#: Items the accountant supplies; everything else is derived.
MANUAL = {'22', '37', '38', '42'}


class VatDeclarationEngine:

    def __init__(self, tax_engine, ledger_engine):
        self._tax = tax_engine
        self._ledger = ledger_engine

    # ==================================================================
    # Public API
    # ==================================================================
    def compute(self, ledger_filter, inputs=None,
                input_vat_expression=DEFAULT_INPUT_VAT,
                output_vat_expression=DEFAULT_OUTPUT_VAT,
                with_diagnostics=True):
        if not ledger_filter.date_from:
            raise ValidationException(
                'A VAT declaration covers a period; date_from is required.')
        inputs = inputs or VatDeclarationInputDTO()

        sales = self._tax.compute_vat_listing(ledger_filter, TaxDirection.SALE)
        purchases = self._tax.compute_vat_listing(ledger_filter,
                                                  TaxDirection.PURCHASE)
        rounding = sales.currency.rounding

        amounts = self._indicators(sales, purchases, inputs, rounding)
        context = self._ledger._load_context(ledger_filter)

        check = None
        if with_diagnostics:
            check = self._reconcile(ledger_filter, context, amounts,
                                    input_vat_expression,
                                    output_vat_expression, rounding)

        lines = tuple(
            FinancialStatementLineDTO(
                code=code, name=name, amount=amounts.get(code, 0.0),
                level=level, sequence=position, bold=bold,
                is_computed=code not in MANUAL,
                note_ref='(nhập tay)' if code in MANUAL else '',
            )
            for position, (code, name, level, bold) in enumerate(LAYOUT)
        )
        return FinancialStatementDTO(
            mapping_code='tt80_01gtgt',
            report_name='Tờ khai thuế giá trị gia tăng',
            report_type='vat_declaration',
            version='01/GTGT',
            company=context['companies'][0],
            currency=sales.currency,
            lines=lines,
            date_from=ledger_filter.date_from,
            date_to=ledger_filter.date_to,
            balance_check=check,
        )

    # ==================================================================
    # The statutory arithmetic
    # ==================================================================
    def _indicators(self, sales, purchases, inputs, rounding):
        by_rate = {group.rate: group for group in sales.groups}

        def base(rate):
            group = by_rate.get(rate)
            return group.base_total if group else 0.0

        def tax(rate):
            group = by_rate.get(rate)
            return group.tax_total if group else 0.0

        amounts = {
            # Mua vào
            '23': purchases.base_total,
            '24': purchases.tax_total,
            # Bán ra, tách theo thuế suất
            '29': base(0.0),
            '30': base(5.0),
            '31': tax(5.0),
            '32': base(10.0),
            '33': tax(10.0),
            # Nhập tay
            '22': inputs.carried_forward,
            '37': inputs.adjustment_decrease,
            '38': inputs.adjustment_increase,
            '42': inputs.refund_claimed,
        }
        # A rate the form has no column for still has to reach the totals, or
        # the declaration would silently understate. It lands in 27 and 28
        # through the listing totals rather than through a rate column.
        amounts['25'] = amounts['24']
        amounts['26'] = 0.0
        amounts['27'] = sales.base_total - amounts['26']
        amounts['28'] = sales.tax_total
        amounts['34'] = amounts['26'] + amounts['27']
        amounts['35'] = amounts['28']
        amounts['36'] = amounts['35'] - amounts['25']

        settled = (amounts['36'] - amounts['22']
                   + amounts['37'] - amounts['38'])
        amounts['40a'] = settled if settled > 0 else 0.0
        amounts['41'] = -settled if settled < 0 else 0.0
        amounts['43'] = amounts['41'] - amounts['42']

        return {code: round_amount(value, rounding)
                for code, value in amounts.items()}

    # ==================================================================
    # Reconciliation against the ledger
    # ==================================================================
    def _reconcile(self, ledger_filter, context, amounts,
                   input_expression, output_expression, rounding):
        """Output VAT on the declaration against the movement on 3331.

        A journal entry crediting the output VAT account by hand produces no tax
        line, so no listing row and no indicator. The declaration would look
        complete and be short by exactly that amount — which is what this
        surfaces.
        """
        accounts = context['accounts']
        output_ids = {a.id for a in
                      AccountExpression.resolve(output_expression, accounts)}
        if not output_ids:
            return None

        balances = self._ledger.compute_balances(ledger_filter, GroupBy.ACCOUNT)
        # Output VAT is a credit, so its movement is negative in the ledger.
        posted = -sum(summary.movement.balance
                      for key, summary in balances.items()
                      if key[0] in output_ids)
        posted = round_amount(posted, rounding)
        declared = amounts.get('28', 0.0)
        difference = round_amount(declared - posted, rounding)

        return BalanceCheckDTO(
            left_code='28',
            right_code='Phát sinh Có tài khoản thuế GTGT đầu ra',
            left_amount=declared, right_amount=posted,
            difference=difference,
            is_balanced=is_zero(difference, rounding),
        )
