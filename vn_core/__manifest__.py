# -*- coding: utf-8 -*-
# Target: Odoo 16.0 Community Edition
{
    'name': 'Vietnam ERP Framework - Core',
    'version': '16.0.1.5.0',
    'category': 'Technical',
    'summary': 'Domain engines, repositories, services and DTOs for VAS reporting',
    'author': 'Manh Nguyen',
    'license': 'AGPL-3',
    'website': 'https://github.com/parabol123654/vn-odoo-framework',
    'support': 'parabol123654@gmail.com',
    'images': ['static/description/banner.png'],
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/vn_report_mapping_views.xml',
    ],
    'installable': True,
    'application': False,
}
