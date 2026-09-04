# -*- coding: utf-8 -*-
# Target: Odoo 14.0 Community Edition
{
    'name': 'Vietnam VAS Reports - Fixed Assets',
    'version': '14.0.1.0.0',
    'category': 'Accounting/Localizations/Reporting',
    'summary': 'Sổ TSCĐ (S21-DN), Thẻ TSCĐ (S23-DN) and Bảng tính và phân bổ '
               'khấu hao (06-TSCĐ) on top of OCA account_asset_management',
    'author': 'Manh Nguyen',
    'license': 'AGPL-3',
    'support': 'parabol123654@gmail.com',
    'images': ['static/description/banner.png'],
    # Split out per Part 16 §4: these reports need an asset subledger, and
    # Odoo 14 Community has none — the data comes from OCA
    # account_asset_management (repo OCA/account-financial-tools, branch
    # 14.0). A company keeping ordinary books without asset accounting has no
    # reason to install that stack.
    'depends': ['vn_core', 'l10n_vn_vas_reports', 'account_asset_management'],
    'data': [
        'security/vn_asset_report_groups.xml',
        'security/ir.model.access.csv',
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
