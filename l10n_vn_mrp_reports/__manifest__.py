# -*- coding: utf-8 -*-
# Target: Odoo 18.0 Community Edition
{
    'name': 'Vietnam VAS Reports - Manufacturing',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations/Reporting',
    'summary': 'Vietnamese production cost reports and the cost card '
               'S37-DN (TT200)',
    'author': 'Manh Nguyen',
    'license': 'AGPL-3',
    'support': 'parabol123654@gmail.com',
    'images': ['static/description/banner.png'],
    # Split out for the same reason as the inventory reports: this needs mrp,
    # and a trading or services company running the accounting books has no
    # reason to install Manufacturing to get them (Part 16 §4).
    'depends': ['vn_core', 'l10n_vn_vas_reports', 'mrp', 'stock_account'],
    'data': [
        'security/vn_mrp_report_groups.xml',
        'security/ir.model.access.csv',
        'report/production_cost_templates.xml',
        'report/report_actions.xml',
        'views/production_cost_wizard_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/vn_demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_vn_mrp_reports/static/src/scss/vn_mrp_report.scss',
        ],
        'web.report_assets_common': [
            'l10n_vn_mrp_reports/static/src/scss/vn_mrp_report.scss',
        ],
    },
    'installable': True,
    'application': False,
}
