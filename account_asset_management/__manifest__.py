# Copyright 2009-2019 Noviat
# Copyright 2019 Tecnativa - Pedro M. Baeza
# Copyright 2021 Tecnativa - João Marques
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# Port of OCA/account-financial-tools 19.0 to 20.0, kept here until OCA
# publishes its own 20.0 branch. The XLSX asset report (and its
# report_xlsx_helper dependency) is left out: the Vietnamese books come from
# l10n_vn_asset_reports.
{
    "name": "Assets Management",
    "version": "20.0.1.0.0",
    "license": "AGPL-3",
    "depends": ["account"],
    "excludes": ["account_asset"],
    "development_status": "Mature",
    "external_dependencies": {"python": ["python-dateutil"]},
    "author": "Noviat, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/account-financial-tools",
    "category": "Accounting & Finance",
    "data": [
        "security/ir.access.csv",
        "wizard/account_asset_compute.xml",
        "wizard/account_asset_remove.xml",
        "views/account_account.xml",
        "views/account_asset.xml",
        "views/account_asset_group.xml",
        "views/account_asset_profile.xml",
        "views/account_move.xml",
        "views/account_move_line.xml",
        "views/menuitem.xml",
        "data/cron.xml",
        "wizard/wiz_asset_move_reverse.xml",
    ],
}
