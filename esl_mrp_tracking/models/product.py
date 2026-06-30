# -*- coding: utf-8 -*-
from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_cylinder = fields.Boolean(
        string='Cylinder',
        default=False,
        help='Check this if the product is a Cylinder.'
    )
