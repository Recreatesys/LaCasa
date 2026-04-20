{
    'name': 'LCS Monthly Statement',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Generate monthly statements aggregating invoices per customer',
    'author': 'Recreatesys',
    'depends': ['account', 'lcs_crm_catering'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/monthly_statement_wizard_views.xml',
        'report/monthly_statement_template.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
