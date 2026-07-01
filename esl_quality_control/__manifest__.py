# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Quality Control (Community)',
    'version': '19.0.0.1',
    'category': 'Supply Chain/Quality',
    'sequence': 120,
    'summary': 'Control the quality of your products (Community Edition)',
    'description': """
Quality Control for Odoo Community
==================================
* Define quality points that will generate quality checks on pickings
* Quality alerts can be created independently or related to quality checks
* Possibility to add a measure to the quality check with a min/max tolerance
* Define your stages for the quality alerts
""",
    'depends': ['stock', 'mail', 'mrp'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/mail_alias_data.xml',
        'data/quality_data.xml',
        'data/quality_control_data.xml',
        'report/worksheet_custom_reports.xml',
        'report/worksheet_custom_report_templates.xml',
        'views/quality_views.xml',
        'views/product_views.xml',
        'views/stock_move_views.xml',
        'views/stock_picking_views.xml',
        'views/mrp_production_views.xml',
        'views/stock_lot_views.xml',
        'wizard/quality_check_wizard_views.xml',
    ],
    'application': True,
    'author': 'ESL / Odoo Community Port',
    'license': 'LGPL-3',
    'assets': {
        'web.assets_backend': [
            'esl_quality_control/static/src/scss/quality_dashboard.scss',
        ],
    }
}
