# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
{
    'name': 'Vietnam VAS Reports - Inventory',
    'version': '14.0.1.0.0',
    'category': 'Accounting/Localizations/Reporting',
    'summary': 'Thẻ kho and Bảng tổng hợp Nhập - Xuất - Tồn (TT200)',
    'author': 'Manh Nguyen',
    'license': 'AGPL-3',
    'support': 'parabol123654@gmail.com',
    'images': ['static/description/banner.png'],
    # A separate module for one reason only: these reports need stock_account,
    # and a trading or services company running the accounting books should not
    # be forced to install Inventory to get them. That is the test Part 16 §4
    # sets for splitting a module, and this is the first time it is met.
    'depends': ['vn_core', 'l10n_vn_reports', 'stock_account'],
    'data': [
        'security/vn_stock_report_groups.xml',
        'security/ir.model.access.csv',
        'views/assets.xml',
        'report/stock_card_templates.xml',
        'report/report_actions.xml',
        'views/stock_card_wizard_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/vn_demo_data.xml',
    ],
    'installable': True,
    'application': False,
}
