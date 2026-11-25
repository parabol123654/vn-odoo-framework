# -*- coding: utf-8 -*-
# Target: Odoo 20.0 Community Edition
{
    'name': 'Vietnam VAS Reports - Fixed Assets',
    'version': '20.0.1.0.0',
    'category': 'Accounting/Localizations/Reporting',
    'summary': 'Vietnamese fixed asset books S21-DN and S23-DN and the '
               'depreciation allocation sheet 06-TSCD, on vn_account_asset '
               '(port of OCA account_asset_management)',
    'author': 'Manh Nguyen',
    'license': 'AGPL-3',
    'website': 'https://github.com/parabol123654/vn-odoo-framework',
    'support': 'parabol123654@gmail.com',
    'images': ['static/description/banner.png'],
    # Split out because these reports need an asset subledger, and
    # Odoo 20 Community has none — the data comes from vn_account_asset, OCA's
    # account_asset_management ported to 20.0 in this repository until OCA
    # publishes its own branch, and renamed because the Apps Store keeps that
    # name for OCA's module. A company keeping ordinary books without asset
    # accounting has no reason to install that stack.
    'depends': ['vn_core', 'l10n_vn_vas_reports', 'vn_account_asset'],
    'data': [
        'security/vn_asset_report_groups.xml',
        'security/ir.access.csv',
        'report/asset_report_templates.xml',
        'report/report_actions.xml',
        'views/asset_report_wizard_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/vn_demo_data.xml',
    ],
    'installable': True,
    'application': False,
}
