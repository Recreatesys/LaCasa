{
    'name': 'LCS CRM Catering',
    'version': '19.0.1.12.0',
    'category': 'Sales/CRM',
    'summary': 'Catering-specific fields for CRM, Sales Orders, and Invoices',
    'author': 'Recreatesys',
    'depends': ['crm', 'sale_crm', 'sale', 'account'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/paperformat.xml',
        'views/res_partner_views.xml',
        'views/crm_lead_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'report/invoice_report_template.xml',
        'report/sale_order_report_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'lcs_crm_catering/static/src/css/chatter.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
