# -*- coding: utf-8 -*-
# Target: Odoo 16.0 Community Edition
{
    'name': 'Vietnam VAS Reports - Inventory',
    'version': '16.0.1.0.0',
    'category': 'Accounting/Localizations/Reporting',
    'summary': 'Vietnamese inventory books: stock card S12-DN, '
               'stock ledger S10-DN, summary S11-DN (TT200, TT133, TT99)',
    'author': 'Manh Nguyen',
    'license': 'AGPL-3',
    'website': 'https://github.com/parabol123654/vn-odoo-framework',
    'support': 'parabol123654@gmail.com',
    'images': ['static/description/banner.png'],
    # A separate module for one reason only: these reports need stock_account,
    # and a trading or services company running the accounting books should not
    # be forced to install Inventory to get them. That is the test for
    # splitting a module out.
    'depends': ['vn_core', 'l10n_vn_vas_reports', 'stock_account'],
    'data': [
        'security/vn_stock_report_groups.xml',
        'security/ir.model.access.csv',
        'report/stock_card_templates.xml',
        'report/report_actions.xml',
        'views/stock_card_wizard_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/vn_demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_vn_stock_reports/static/src/scss/vn_stock_report.scss',
        ],
        'web.report_assets_common': [
            'l10n_vn_stock_reports/static/src/scss/vn_stock_report.scss',
        ],
    },
    'installable': True,
    'application': False,
}
