# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
"""Demo fixed assets for the asset reports.

Three assets on two profiles, depreciating monthly since the start of the
year, entries posted up to today through the subledger's own flow — so S21-DN
has accumulated depreciation, S23-DN has year rows, and 06-TSCĐ has both a
prior period and an asset that arrived mid-year (chỉ tiêu II).

Runs once; posted depreciation cannot be unlinked, so a rerun reports itself
as already loaded. Marker: any asset coded ``VNDEMO-TS1``.
"""

from datetime import date

from odoo import api, fields, models

#: key -> (prefixes best-first, (code, name, account_type) to create when the
#: chart has none — a database running on the generator-made chart has no
#: 211/214 to find). account_type is the Odoo 16+ selection.
_ACCOUNTS = {
    'asset_machine': (('2112', '211'), (
        '211', 'Tài sản cố định hữu hình', 'asset_fixed')),
    'asset_office': (('2114', '211'), (
        '211', 'Tài sản cố định hữu hình', 'asset_fixed')),
    'depreciation': (('2141', '214'), (
        '214', 'Hao mòn tài sản cố định', 'asset_fixed')),
    'expense_factory': (('6274', '627', '642'), (
        '627', 'Chi phí sản xuất chung', 'expense')),
    'expense_office': (('6424', '642'), (
        '642', 'Chi phí quản lý kinh doanh', 'expense')),
}


class VnAssetDemoGenerator(models.AbstractModel):
    _name = 'vn.demo.asset.generator'
    _description = 'Vietnam VAS Demo Data - Fixed Assets'

    @api.model
    def generate(self, company=None):
        company = company or self.env.company
        Asset = self.env['account.asset']
        if Asset.search([('code', '=', 'VNDEMO-TS1')], limit=1):
            return {'company': company.name, 'skipped': True}

        machines, office = self._ensure_profiles(company)
        today = fields.Date.context_today(self)
        year_start = date(today.year, 1, 1)
        month_start = today.replace(day=1)

        specs = (
            ('VNDEMO-TS1', 'Máy ép gỗ thuỷ lực', machines,
             240000000.0, 10, year_start),
            # Arrives this month: the "tăng trong kỳ" line of 06-TSCĐ.
            ('VNDEMO-TS2', 'Máy cưa CNC', machines,
             90000000.0, 5, month_start),
            ('VNDEMO-TS3', 'Máy photocopy văn phòng', office,
             18000000.0, 3, year_start),
        )
        assets = Asset
        for code, name, profile, value, years, start in specs:
            assets |= Asset.create({
                'name': name,
                'code': code,
                'profile_id': profile.id,
                'purchase_value': value,
                'date_start': start,
                'method_number': years,
            })
        assets.compute_depreciation_board()
        assets.validate()
        assets._compute_entries(today)
        return {'company': company.name, 'skipped': False,
                'assets': len(assets)}

    # ------------------------------------------------------------------
    def _account(self, company, key):
        Account = self.env['account.account'].with_company(company)
        prefixes, (code, name, account_type) = _ACCOUNTS[key]
        for prefix in prefixes:
            account = Account.search([
                ('company_ids', 'in', [company.id]),
                ('code', '=like', prefix + '%'),
            ], order='code', limit=1)
            if account:
                return account
        return Account.create({
            'code': code,
            'name': name,
            'account_type': account_type,
        })

    def _ensure_profiles(self, company):
        journal = self.env['account.journal'].search([
            ('company_id', '=', company.id), ('type', '=', 'general')],
            limit=1)
        Profile = self.env['account.asset.profile']

        def profile(name, asset_key, expense_key):
            return Profile.create({
                'name': name,
                'account_asset_id': self._account(company, asset_key).id,
                'account_depreciation_id':
                    self._account(company, 'depreciation').id,
                'account_expense_depreciation_id':
                    self._account(company, expense_key).id,
                'journal_id': journal.id,
                'method': 'linear',
                'method_time': 'year',
                'method_period': 'month',
            })

        return (profile('VAS demo - Máy móc, thiết bị',
                        'asset_machine', 'expense_factory'),
                profile('VAS demo - Thiết bị quản lý',
                        'asset_office', 'expense_office'))
