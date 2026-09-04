# -*- coding: utf-8 -*-
"""Fixed Asset Engine — Sổ TSCĐ, Thẻ TSCĐ and Bảng phân bổ khấu hao.

Pure Python: assets, depreciation lines and the currency all arrive through
``IAssetRepository``.

What counts as depreciation is decided once, in :meth:`_counted`: a line whose
journal entry exists, or an initial-balance line the subledger posts no entry
for. The rest of the schedule is a forecast, and a statutory book that quietly
mixed forecast into recorded figures would disagree with account 214 — which
is the one thing these reports must never do. ``include_unposted`` widens the
reports to the full plan explicitly, for whoever wants to see ahead.

TT200 note: S21-DN carries "nước sản xuất" and "năm sản xuất" columns. The
subledger stores neither, so the engine does not invent them and the template
prints them blank.
"""

import calendar
from datetime import date as date_type, timedelta

from ...core.exceptions import ValidationException
from ...core.utils.number import is_zero, round_amount
from ...dto.asset import (
    AllocationSummaryDTO, AssetCardDTO, AssetCardYearDTO, AssetCardsDTO,
    AssetRegisterDTO, AssetRegisterGroupDTO, AssetRegisterRowDTO,
    DepreciationAllocationDTO, DepreciationAllocationRowDTO,
)

#: Roots are cấp 1 accounts in the Vietnamese chart.
ROOT_LENGTH = 3


class AssetEngine:

    def __init__(self, repository):
        self._repo = repository

    # ==================================================================
    # Sổ TSCĐ (S21-DN)
    # ==================================================================
    def compute_register(self, asset_filter):
        """One row per asset, grouped by nhóm TSCĐ.

        An asset is on the register when it existed at any point of the
        period: started on or before ``date_to`` and, when a ``date_from`` is
        given, not removed before it. An asset removed inside the period stays
        on the page with its removal shown — that is what the "ghi giảm"
        columns exist for.
        """
        self._validate(asset_filter)
        currency = self._repo.get_currency(asset_filter.company_ids)
        rounding = currency.rounding

        profiles = {p.id: p for p in self._repo.get_profiles(asset_filter)}
        assets = [asset for asset in self._repo.get_assets(asset_filter)
                  if self._in_period(asset, asset_filter)]
        counted = self._counted_amounts(
            assets, asset_filter, upper=asset_filter.date_to)

        buckets = {}
        for asset in assets:
            accumulated = round_amount(counted.get(asset.id, 0.0), rounding)
            buckets.setdefault(asset.profile_id, []).append(
                AssetRegisterRowDTO(
                    asset=asset,
                    accumulated=accumulated,
                    residual=round_amount(asset.purchase_value - accumulated,
                                          rounding),
                ))

        groups = []
        for profile_id, rows in buckets.items():
            profile = profiles.get(profile_id)
            if profile is None:
                continue
            rows.sort(key=lambda r: (r.asset.date_start or '',
                                     r.asset.code, r.asset.name))
            groups.append(AssetRegisterGroupDTO(
                profile=profile,
                rows=tuple(rows),
                total_purchase=round_amount(
                    sum(r.asset.purchase_value for r in rows), rounding),
                total_accumulated=round_amount(
                    sum(r.accumulated for r in rows), rounding),
                total_residual=round_amount(
                    sum(r.residual for r in rows), rounding),
            ))
        groups.sort(key=lambda g: g.profile.name)

        return AssetRegisterDTO(
            groups=tuple(groups),
            total_purchase=round_amount(
                sum(g.total_purchase for g in groups), rounding),
            total_accumulated=round_amount(
                sum(g.total_accumulated for g in groups), rounding),
            total_residual=round_amount(
                sum(g.total_residual for g in groups), rounding),
            currency=currency,
        )

    # ==================================================================
    # Thẻ TSCĐ (S23-DN)
    # ==================================================================
    def compute_cards(self, asset_filter):
        """One card per asset, depreciation summed per year.

        The card is the asset's whole life up to ``date_to`` — a Thẻ TSCĐ is
        opened when the asset arrives and follows it to removal, so the
        filter's ``date_from`` deliberately plays no part here.
        """
        self._validate(asset_filter)
        currency = self._repo.get_currency(asset_filter.company_ids)
        rounding = currency.rounding

        profiles = {p.id: p for p in self._repo.get_profiles(asset_filter)}
        assets = [asset for asset in self._repo.get_assets(asset_filter)
                  if not asset.date_start
                  or asset.date_start <= asset_filter.date_to]
        lines = self._repo.get_lines(tuple(a.id for a in assets),
                                     date_to=asset_filter.date_to)

        by_asset = {}
        for line in lines:
            if line.line_type != 'depreciate':
                continue
            if not (line.counted or asset_filter.include_unposted):
                continue
            by_asset.setdefault(line.asset_id, {})
            year_bucket = by_asset[line.asset_id]
            year_bucket[line.date.year] = (
                year_bucket.get(line.date.year, 0.0) + line.amount)

        cards = []
        for asset in assets:
            years, cumulative = [], 0.0
            for year in sorted(by_asset.get(asset.id, {})):
                amount = by_asset[asset.id][year]
                cumulative += amount
                years.append(AssetCardYearDTO(
                    year=year,
                    amount=round_amount(amount, rounding),
                    cumulative=round_amount(cumulative, rounding),
                ))
            accumulated = round_amount(cumulative, rounding)
            cards.append(AssetCardDTO(
                asset=asset,
                profile=profiles.get(asset.profile_id),
                years=tuple(years),
                accumulated=accumulated,
                residual=round_amount(asset.purchase_value - accumulated,
                                      rounding),
            ))
        cards.sort(key=lambda c: (c.asset.code, c.asset.name))
        return AssetCardsDTO(cards=tuple(cards), currency=currency)

    # ==================================================================
    # Bảng tính và phân bổ khấu hao (06-TSCĐ)
    # ==================================================================
    def compute_allocation(self, asset_filter):
        """Nhóm TSCĐ rows against expense-account columns, plus the I–IV
        summary.

        Each cell is depreciation recorded in the period, split by the account
        it was actually charged to. The summary compares against the preceding
        period of equal length: I is what that period recorded, II the current
        depreciation of assets that started depreciating this period, III the
        prior depreciation of assets that stopped, IV the current total. All
        four are measured, none derived, so I + II − III differing from IV is
        information — a recomputed schedule, a rate change — not an error to
        hide.
        """
        self._validate(asset_filter)
        if not asset_filter.date_from:
            raise ValidationException(
                'The allocation sheet is a period document; date_from is '
                'required.')
        currency = self._repo.get_currency(asset_filter.company_ids)
        rounding = currency.rounding

        profiles = {p.id: p for p in self._repo.get_profiles(asset_filter)}
        assets = {a.id: a for a in self._repo.get_assets(asset_filter)}
        current = self._depreciation_between(
            tuple(assets), asset_filter,
            asset_filter.date_from, asset_filter.date_to)

        previous_from, previous_to = self._previous_window(
            asset_filter.date_from, asset_filter.date_to)
        previous = self._depreciation_between(
            tuple(assets), asset_filter, previous_from, previous_to)
        opened_before = self._counted_amounts(
            assets.values(), asset_filter, upper=previous_to)

        cells, column_roots = {}, set()
        for line in current:
            asset = assets.get(line.asset_id)
            if asset is None:
                continue
            root = (line.expense_code or '')[:ROOT_LENGTH]
            column_roots.add(root)
            key = (asset.profile_id, root)
            cells[key] = cells.get(key, 0.0) + line.amount

        columns = tuple(sorted(column_roots, key=lambda r: (not r, r)))
        rows = []
        for profile_id in sorted({pid for pid, _ in cells},
                                 key=lambda pid: profiles[pid].name
                                 if pid in profiles else ''):
            profile = profiles.get(profile_id)
            if profile is None:
                continue
            amounts = tuple(
                round_amount(cells.get((profile_id, column), 0.0), rounding)
                for column in columns)
            rows.append(DepreciationAllocationRowDTO(
                profile=profile,
                amounts=amounts,
                total=round_amount(sum(amounts), rounding),
            ))

        column_totals = tuple(
            round_amount(sum(row.amounts[i] for row in rows), rounding)
            for i in range(len(columns)))
        grand_total = round_amount(sum(column_totals), rounding)

        current_by_asset, previous_by_asset = {}, {}
        for line in current:
            current_by_asset[line.asset_id] = (
                current_by_asset.get(line.asset_id, 0.0) + line.amount)
        for line in previous:
            previous_by_asset[line.asset_id] = (
                previous_by_asset.get(line.asset_id, 0.0) + line.amount)

        increase = sum(
            amount for asset_id, amount in current_by_asset.items()
            if is_zero(opened_before.get(asset_id, 0.0), rounding))
        decrease = sum(
            amount for asset_id, amount in previous_by_asset.items()
            if asset_id not in current_by_asset)

        summary = AllocationSummaryDTO(
            previous_total=round_amount(
                sum(previous_by_asset.values()), rounding),
            increase=round_amount(increase, rounding),
            decrease=round_amount(decrease, rounding),
            current_total=grand_total,
        )
        return DepreciationAllocationDTO(
            columns=columns,
            rows=tuple(rows),
            column_totals=column_totals,
            grand_total=grand_total,
            summary=summary,
            currency=currency,
        )

    # ==================================================================
    # Internals
    # ==================================================================
    @staticmethod
    def _validate(asset_filter):
        if not asset_filter.company_ids:
            raise ValidationException('No company supplied in the filter.')
        if (asset_filter.date_from
                and asset_filter.date_from > asset_filter.date_to):
            raise ValidationException('date_from must precede date_to.')

    @staticmethod
    def _previous_window(date_from, date_to):
        """The "kỳ trước" of 06-TSCĐ.

        The form is a monthly (sometimes quarterly) document, so when the
        period is whole calendar months the previous period is the preceding
        run of the same number of months — sliding back by a raw day count
        would drag the last posting of the month before into the comparison.
        Any other span falls back to the equal-length window ending the day
        before.
        """
        month_aligned = (
            date_from.day == 1
            and date_to.day == calendar.monthrange(date_to.year,
                                                   date_to.month)[1])
        previous_to = date_from - timedelta(days=1)
        if month_aligned:
            months = ((date_to.year - date_from.year) * 12
                      + date_to.month - date_from.month + 1)
            start_index = (date_from.year * 12 + date_from.month - 1) - months
            year, month = divmod(start_index, 12)
            return date_type(year, month + 1, 1), previous_to
        return previous_to - (date_to - date_from), previous_to

    @staticmethod
    def _in_period(asset, asset_filter):
        if asset.date_start and asset.date_start > asset_filter.date_to:
            return False
        if (asset_filter.date_from and asset.date_remove
                and asset.date_remove < asset_filter.date_from):
            return False
        return True

    @staticmethod
    def _counts(line, asset_filter):
        return line.counted or asset_filter.include_unposted

    def _counted_amounts(self, assets, asset_filter, upper):
        """``{asset_id: depreciation recorded up to and including upper}``."""
        lines = self._repo.get_lines(
            tuple(a.id for a in assets), date_to=upper)
        totals = {}
        for line in lines:
            if line.line_type != 'depreciate':
                continue
            if not self._counts(line, asset_filter):
                continue
            totals[line.asset_id] = totals.get(line.asset_id, 0.0) + line.amount
        return totals

    def _depreciation_between(self, asset_ids, asset_filter, date_from,
                              date_to):
        return tuple(
            line for line in self._repo.get_lines(
                asset_ids, date_from=date_from, date_to=date_to)
            if line.line_type == 'depreciate'
            and self._counts(line, asset_filter))
