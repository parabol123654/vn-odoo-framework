# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
"""Odoo implementation of ``IAssetRepository``.

Reads the asset subledger of OCA ``account_asset_management``:
``account.asset``, ``account.asset.line`` and ``account.asset.profile``.

Which account a depreciation was charged to is read from the **posted journal
entry** whenever one exists, and only falls back to the profile's default for
initial-balance and forecast lines. A profile can be repointed after the fact;
the entry is what the ledger saw.
"""

from odoo.addons.vn_core.domain.asset.repository import IAssetRepository
from odoo.addons.vn_core.dto.asset import (
    AssetDTO, AssetLineDTO, AssetProfileDTO,
)
from odoo.addons.vn_core.dto.common import CurrencyDTO
from odoo.addons.vn_core.infrastructure.base_repository import BaseRepository


class OdooAssetRepository(IAssetRepository, BaseRepository):

    def get_currency(self, company_ids):
        company = self.env['res.company'].browse(list(company_ids))[:1]
        currency = company.currency_id or self.env.company.currency_id
        return CurrencyDTO(
            id=currency.id, name=currency.name,
            rounding=currency.rounding, decimal_places=currency.decimal_places)

    # ------------------------------------------------------------------
    def get_profiles(self, asset_filter):
        domain = [('company_id', 'in', list(asset_filter.company_ids))]
        if asset_filter.profile_ids:
            domain.append(('id', 'in', list(asset_filter.profile_ids)))
        profiles = self.env['account.asset.profile'].search(domain)
        return tuple(
            AssetProfileDTO(
                id=profile.id,
                name=profile.name or '',
                asset_account_code=profile.account_asset_id.code or '',
                depreciation_account_code=(
                    profile.account_depreciation_id.code or ''),
                expense_account_code=(
                    profile.account_expense_depreciation_id.code or ''),
            )
            for profile in profiles
        )

    # ------------------------------------------------------------------
    def get_assets(self, asset_filter):
        domain = [
            ('company_id', 'in', list(asset_filter.company_ids)),
            # Draft assets are not in the books. Removed ones are: their
            # closing story is exactly what the "ghi giảm" columns print.
            ('state', 'in', ['open', 'close', 'removed']),
        ]
        if asset_filter.asset_ids:
            domain.append(('id', 'in', list(asset_filter.asset_ids)))
        if asset_filter.profile_ids:
            domain.append(('profile_id', 'in', list(asset_filter.profile_ids)))
        assets = self.env['account.asset'].with_context(
            active_test=False).search(domain)
        return tuple(
            AssetDTO(
                id=asset.id,
                name=asset.name or '',
                code=asset.code or '',
                profile_id=asset.profile_id.id,
                state=asset.state,
                purchase_value=asset.purchase_value,
                salvage_value=asset.salvage_value,
                date_start=asset.date_start,
                date_remove=asset.date_remove,
                method=asset.method,
                method_number=asset.method_number,
                method_period=asset.method_period,
                acquisition_ref=(
                    asset.account_move_line_ids[:1].move_id.name or ''),
            )
            for asset in assets
        )

    # ------------------------------------------------------------------
    def get_lines(self, asset_ids, date_from=None, date_to=None):
        if not asset_ids:
            return ()
        domain = [('asset_id', 'in', list(asset_ids)),
                  ('type', '!=', 'create')]
        if date_from:
            domain.append(('line_date', '>=', date_from))
        if date_to:
            domain.append(('line_date', '<=', date_to))
        lines = self.env['account.asset.line'].search(
            domain, order='line_date, id')

        expense_codes = self._expense_codes(lines)
        return tuple(
            AssetLineDTO(
                id=line.id,
                asset_id=line.asset_id.id,
                date=line.line_date,
                amount=line.amount,
                line_type=line.type,
                posted=bool(line.move_id) and line.move_id.state == 'posted',
                init=line.init_entry,
                move_name=line.move_id.name or '',
                expense_code=expense_codes.get(
                    line.move_id.id,
                    line.asset_id.profile_id
                        .account_expense_depreciation_id.code or ''),
            )
            for line in lines
        )

    def _expense_codes(self, lines):
        """``{move_id: debit account code}`` for the posted entries.

        A depreciation entry debits one expense account and credits the
        accumulated-depreciation account, so "the debit side" identifies it.
        The largest debit wins on the rare multi-line entry.
        """
        move_ids = tuple({line.move_id.id for line in lines if line.move_id})
        if not move_ids:
            return {}
        self.env['account.move.line'].flush()
        self.cr.execute("""
            SELECT DISTINCT ON (aml.move_id)
                   aml.move_id AS move_id,
                   aa.code     AS code
              FROM account_move_line aml
              JOIN account_account aa ON aa.id = aml.account_id
             WHERE aml.move_id IN %s
               AND aml.debit > 0
          ORDER BY aml.move_id, aml.debit DESC
        """, (move_ids,))
        return {row['move_id']: row['code'] or ''
                for row in self.cr.dictfetchall()}
