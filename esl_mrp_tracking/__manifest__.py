# -*- coding: utf-8 -*-
{
    'name': 'ESL MRP Tracking',
    'version': '19.0',
    'summary': 'Track Customers in Bills of Material (BOM) and Manufacturing Orders (MO)',
    'description': """
        This module adds a Customer field on Bill of Materials and Manufacturing Orders,
        linking them and propagating the Customer to stock transfers as the Assign Owner.
    """,
    'category': 'Manufacturing/Manufacturing',
    'author': 'Antigravity',
    'depends': ['mrp', 'sale_mrp', 'stock'],
    'data': [
        'views/mrp_bom_views.xml',
        'views/mrp_production_views.xml',
        'views/product_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
