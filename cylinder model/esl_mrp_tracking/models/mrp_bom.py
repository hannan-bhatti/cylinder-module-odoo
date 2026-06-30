# -*- coding: utf-8 -*-
from odoo import fields, models

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        help='Customer associated with this Bill of Material (BOM) / Project.'
    )
