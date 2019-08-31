# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'Discount Setup',
    'version' : '10.0.1',
    'summary': 'This app helps you to setup discount.',
    'description': "Discount",
    'category': 'Accounting',
    'author': 'SAGAR JAYSWAL',
    'website': 'http://www.sagarcs.com',
    'license': 'AGPL-3',
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/acc_view.xml',
        'views/discount_report_report.xml',
        'views/report_discount.xml',
        'reports/discount_report_view.xml',
        
    ],
    'depends': ['base','account','sale','product'],
    'installable': True,
    'application': False,
    'auto_install': False,
    
}
