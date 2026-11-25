# Copyright 2009-2019 Noviat
# Copyright 2019 Tecnativa - Pedro M. Baeza
# Copyright 2021 Tecnativa - João Marques
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# Port of OCA/account-financial-tools 19.0 account_asset_management to 20.0,
# kept here until OCA publishes its own 20.0 branch. The XLSX asset report
# (and its report_xlsx_helper dependency) is left out: the Vietnamese books
# come from l10n_vn_asset_reports.
#
# Renamed from account_asset_management because the Odoo Apps Store reserves
# that technical name for OCA's module and refuses another one under it. The
# two must never be installed together, hence "excludes".
#
# Once OCA publishes 20.0, a company can move to OCA's module: the models,
# fields and tables are the same. It is still a migration, not a drop-in
# swap: the ir_module_module row and every ir_model_data record (XML ids of
# views, actions, menus, access rules, fields, translations) are registered
# under vn_account_asset and have to be renamed to account_asset_management
# (and its dependents' manifests switched) before OCA's module is installed;
# otherwise Odoo treats them as another module's records and recreates them
# a second time. Rehearse it on a copy of the database.
{
    "name": "Assets Management (Vietnam, port of OCA account_asset_management)",
    "version": "20.0.1.0.0",
    "license": "AGPL-3",
    "depends": ["account"],
    "excludes": ["account_asset", "account_asset_management"],
    "development_status": "Mature",
    "external_dependencies": {"python": ["python-dateutil"]},
    "author": "Noviat, Odoo Community Association (OCA), Manh Nguyen",
    # This repository, not OCA's: the port and its issues are maintained here.
    "website": "https://github.com/parabol123654/vn-odoo-framework",
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
