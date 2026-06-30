# -*- coding: utf-8 -*-
from odoo import api, models

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super(StockPicking, self).create(vals_list)
        for picking in pickings:
            mo = (picking.move_ids.raw_material_production_id | picking.move_ids.production_id)[:1]
            if mo and mo.partner_id and not picking.owner_id:
                picking.owner_id = mo.partner_id
        return pickings

    def write(self, vals):
        res = super(StockPicking, self).write(vals)
        if 'move_ids' in vals or 'move_ids_without_package' in vals:
            for picking in self:
                mo = (picking.move_ids.raw_material_production_id | picking.move_ids.production_id)[:1]
                if mo and mo.partner_id and not picking.owner_id:
                    picking.write({'owner_id': mo.partner_id.id})
        return res
