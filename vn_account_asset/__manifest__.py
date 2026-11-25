# Copyright 2009-2019 Noviat
# Copyright 2019 Tecnativa - Pedro M. Baeza
# Copyright 2021 Tecnativa - João Marques
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# OCA/account-financial-tools 17.0 account_asset_management (17.0.1.2.2, commit
# 8a83b97d6180), vendored here so the fixed-asset books install from this
# repository alone. The XLSX asset report, the asset analysis report and
# the report_xlsx_helper dependency are left out: the Vietnamese books come
# from l10n_vn_asset_reports. The rest is OCA's code, unchanged apart from
# the module name.
#
# Renamed from account_asset_management because the Odoo Apps Store reserves
# that technical name for OCA's module and refuses another one under it. The
# two must never be installed together, hence "excludes".
#
# Moving a database between OCA's module and this one (either way) is a
# migration, not a drop-in swap: the models, fields and tables are the same,
# but the ir_module_module row and every ir_model_data record (XML ids of
# views, actions, menus, access rules, fields, translations) are registered
# under the installed module's name and have to be renamed to the other one
# (and its dependents' manifests switched) before the other module is
# installed; otherwise Odoo treats them as another module's records and
# creates them a second time. Rehearse it on a copy of the database.
{
    "name": "Assets Management (Vietnam, port of OCA account_asset_management)",
    "version": "17.0.1.0.0",
    "license": "AGPL-3",
    "depends": ["account"],
    "excludes": ["account_asset", "account_asset_management"],
    "development_status": "Mature",
    "external_dependencies": {"python": ["python-dateutil"]},
    "author": "Noviat, Odoo Community Association (OCA), Manh Nguyen",
    # This repository, not OCA's: this copy and its issues are maintained here.
    "website": "https://github.com/parabol123654/vn-odoo-framework",
    "category": "Accounting & Finance",
    "data": [
        "security/account_asset_security.xml",
        "security/ir.model.access.csv",
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
