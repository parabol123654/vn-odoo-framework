# -*- coding: utf-8 -*-
"""Tax Engine — Bảng kê hoá đơn GTGT (Part 1 §5.1, Engine 4).

Groups invoices by VAT rate, normalises signs, and totals. It never reads the
database: an ``ITaxRepository`` supplies rows that already represent one invoice
and one rate.

Pure Python: no Odoo, no SQL.
"""

from ...core.enums import TaxDirection
from ...core.exceptions import ValidationException
from ...core.utils.number import round_amount
from ...dto.tax import TaxRateGroupDTO, VatListingDTO
from .calculators.vat_sign import VatSignCalculator


class TaxEngine:

    def __init__(self, repository):
        self._repo = repository

    # ==================================================================
    # Public API
    # ==================================================================
    def compute_vat_listing(self, ledger_filter, direction=TaxDirection.SALE):
        """Bảng kê hoá đơn, hàng hoá dịch vụ bán ra / mua vào."""
        if not ledger_filter.company_ids:
            raise ValidationException('No company supplied in the filter.')
        if ledger_filter.date_from and ledger_filter.date_from > ledger_filter.date_to:
            raise ValidationException('date_from must precede date_to.')

        currency = self._repo.get_currency(ledger_filter.company_ids)
        rounding = currency.rounding
        factor = VatSignCalculator.factor(direction)

        buckets = {}
        for row in self._repo.get_tax_lines(ledger_filter, direction):
            line = row._replace(
                base_amount=round_amount(row.base_amount * factor, rounding),
                tax_amount=round_amount(row.tax_amount * factor, rounding),
            )
            buckets.setdefault(row.tax_rate, []).append(line)

        groups = []
        for rate in sorted(buckets):
            lines = sorted(buckets[rate],
                           key=lambda l: (l.invoice_date, l.invoice_number,
                                          l.move_id))
            groups.append(TaxRateGroupDTO(
                rate=rate,
                label=self._rate_label(rate),
                lines=tuple(lines),
                base_total=round_amount(sum(l.base_amount for l in lines),
                                        rounding),
                tax_total=round_amount(sum(l.tax_amount for l in lines),
                                       rounding),
            ))

        invoices = {l.move_id for g in groups for l in g.lines}
        return VatListingDTO(
            direction=direction.value,
            groups=tuple(groups),
            base_total=round_amount(sum(g.base_total for g in groups), rounding),
            tax_total=round_amount(sum(g.tax_total for g in groups), rounding),
            currency=currency,
            date_from=ledger_filter.date_from,
            date_to=ledger_filter.date_to,
            invoice_count=len(invoices),
        )

    # ==================================================================
    # Internals
    # ==================================================================
    @staticmethod
    def _rate_label(rate):
        """Vietnamese filings label a 0% block separately from an exempt one.

        The ledger cannot tell them apart on rate alone — both compute to zero
        tax — so a 0% rate is labelled as such and any finer distinction is left
        to the tax configuration.
        """
        if not rate:
            return 'Thuế suất 0% hoặc không chịu thuế'
        if float(rate).is_integer():
            return 'Thuế suất %d%%' % int(rate)
        return 'Thuế suất %s%%' % ('%.2f' % rate).rstrip('0').rstrip('.')
