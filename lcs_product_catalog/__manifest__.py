{
    'name': 'LCS Product Catalog',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Dish master data, set menus, and SO set expansion with dish selection',
    'author': 'Recreatesys',
    'depends': ['sale', 'lcs_crm_catering'],
    'data': [
        'security/ir.model.access.csv',
        'data/master_dishes.xml',
        'views/catering_set_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
