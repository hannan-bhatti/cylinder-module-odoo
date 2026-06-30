# -*- coding: utf-8 -*-
from odoo import api, fields, models

class StockMove(models.Model):
    _inherit = 'stock.move'

    is_cylinder_move = fields.Boolean(
        string='Is Cylinder Move',
        default=False,
        help='Indicates if this move is for a cylinder selected on the manufacturing order.'
    )

    @api.model_create_multi
    def create(self, vals_list):
        moves = super(StockMove, self).create(vals_list)
        for move in moves:
            production = move.raw_material_production_id or move.production_id
            if production and production.partner_id and not move.restrict_partner_id:
                move.restrict_partner_id = production.partner_id
        return moves

    def write(self, vals):
        res = super(StockMove, self).write(vals)
        if any(f in vals for f in ['raw_material_production_id', 'production_id']):
            for move in self:
                production = move.raw_material_production_id or move.production_id
                if production and production.partner_id and not move.restrict_partner_id:
                    move.restrict_partner_id = production.partner_id
        return res
