# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.fields import Command

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        compute='_compute_partner_id',
        store=True,
        readonly=False,
        help='Customer associated with this Manufacturing Order (MO).'
    )

    cylinder_id = fields.Many2one(
        'product.product',
        string='Cylinder',
        domain="[('is_cylinder', '=', True)]",
        compute='_compute_cylinder_id',
        store=True,
        readonly=False,
        help='Select Cylinder for this manufacturing order.'
    )

    bom_id = fields.Many2one(
        'mrp.bom',
        domain="""[
            ('company_id', 'in', [company_id, False]),
            '|',
                ('product_id', '=', product_id),
                '&',
                    ('product_tmpl_id.product_variant_ids', '=', product_id),
                    ('product_id', '=', False),
            ('type', '=', 'normal'),
            ('partner_id', 'in', [partner_id, False])
        ]"""
    )

    @api.depends('sale_line_id', 'origin')
    def _compute_cylinder_id(self):
        for production in self:
            sale_order = False
            if production.sale_line_id:
                sale_order = production.sale_line_id.order_id
            elif production.origin:
                sale_order = self.env['sale.order'].search([('name', '=', production.origin)], limit=1)

            if sale_order:
                cylinder_line = sale_order.order_line.filtered(lambda l: l.product_id.is_cylinder)[:1]
                if cylinder_line:
                    production.cylinder_id = cylinder_line.product_id
                else:
                    if not production.cylinder_id:
                        production.cylinder_id = False
            else:
                if not production.cylinder_id:
                    production.cylinder_id = False

    @api.depends('sale_line_id', 'sale_line_id.order_id.partner_id', 'origin')
    def _compute_partner_id(self):
        for production in self:
            if production.sale_line_id:
                production.partner_id = production.sale_line_id.order_id.partner_id
            elif production.origin:
                # If created from procurement/replenishment where sale_line_id is not set
                sale_order = self.env['sale.order'].search([('name', '=', production.origin)], limit=1)
                if sale_order:
                    production.partner_id = sale_order.partner_id
                else:
                    if not production.partner_id:
                        production.partner_id = False
            else:
                if not production.partner_id:
                    production.partner_id = False

    @api.depends('bom_id', 'product_id', 'product_qty', 'product_uom_id', 'partner_id', 'sale_line_id', 'origin', 'cylinder_id')
    def _compute_move_raw_ids(self):
        # We clean the custom moves (moves that have a sale_line_id or is_cylinder_move) before calling super
        # so standard Odoo doesn't touch or duplicate them.
        custom_moves_by_production = {}
        cylinder_moves_by_production = {}
        for production in self:
            custom_moves = production.move_raw_ids.filtered(lambda m: m.sale_line_id)
            cylinder_moves = production.move_raw_ids.filtered(lambda m: m.is_cylinder_move)

            unlink_commands = []
            if custom_moves:
                custom_moves_by_production[production.id] = custom_moves
                unlink_commands.extend([Command.unlink(m.id) for m in custom_moves])
            if cylinder_moves:
                cylinder_moves_by_production[production.id] = cylinder_moves
                unlink_commands.extend([Command.unlink(m.id) for m in cylinder_moves])

            if unlink_commands:
                production.move_raw_ids = unlink_commands

        # Call super to generate/update BOM moves
        super(MrpProduction, self)._compute_move_raw_ids()

        # Now restore, update, create, or delete the custom moves and cylinder moves
        for production in self:
            if production.state != 'draft' or self.env.context.get('skip_compute_move_raw_ids'):
                # If not draft, just link back the custom moves and cylinder moves we unlinked
                link_commands = []
                if production.id in custom_moves_by_production:
                    link_commands.extend([Command.link(m.id) for m in custom_moves_by_production[production.id]])
                if production.id in cylinder_moves_by_production:
                    link_commands.extend([Command.link(m.id) for m in cylinder_moves_by_production[production.id]])
                if link_commands:
                    production.move_raw_ids = link_commands
                continue

            list_commands = []

            # 1. Handle Custom Moves from Sale Order
            sale_order = False
            if production.sale_line_id:
                sale_order = production.sale_line_id.order_id
            elif production.origin:
                sale_order = self.env['sale.order'].search([('name', '=', production.origin)], limit=1)

            # Get previously existing custom moves
            existing_custom_moves = custom_moves_by_production.get(production.id, self.env['stock.move'])
            # Also look if any custom moves are currently linked
            linked_custom_moves = production.move_raw_ids.filtered(lambda m: m.sale_line_id)
            all_existing_custom = existing_custom_moves | linked_custom_moves

            if not sale_order:
                # If no sale order, delete all custom moves
                if all_existing_custom:
                    list_commands.extend([Command.delete(m.id) for m in all_existing_custom])
            else:
                # Generate expected custom moves from SO lines
                expected_custom_vals = []
                for line in sale_order.order_line:
                    # Skip finished product to prevent loops
                    if line.product_id == production.product_id:
                        continue
                    # Skip non-product lines
                    if line.display_type or not line.product_id:
                        continue
                    # Only include consumable/storable products
                    if line.product_id.type != 'consu':
                        continue

                    raw_move_vals = production._get_move_raw_values(
                        line.product_id,
                        line.product_uom_qty,
                        line.product_uom,
                    )
                    raw_move_vals['sale_line_id'] = line.id
                    if production.partner_id:
                        raw_move_vals['restrict_partner_id'] = production.partner_id.id
                    expected_custom_vals.append(raw_move_vals)

                existing_custom_by_line = {m.sale_line_id.id: m for m in all_existing_custom}
                seen_line_ids = set()

                for vals in expected_custom_vals:
                    line_id = vals['sale_line_id']
                    seen_line_ids.add(line_id)
                    if line_id in existing_custom_by_line:
                        move = existing_custom_by_line[line_id]
                        # Update if quantity or product/uom changed
                        update_vals = {}
                        if move.product_uom_qty != vals['product_uom_qty']:
                            update_vals['product_uom_qty'] = vals['product_uom_qty']
                        if move.product_uom != vals['product_uom']:
                            update_vals['product_uom'] = vals['product_uom']
                        if production.partner_id and move.restrict_partner_id != production.partner_id:
                            update_vals['restrict_partner_id'] = production.partner_id.id
                        if update_vals:
                            list_commands.append(Command.update(move.id, update_vals))
                        else:
                            # Re-link the existing move if it was unlinked
                            if move not in production.move_raw_ids:
                                list_commands.append(Command.link(move.id))
                    else:
                        # Create new custom move
                        list_commands.append(Command.create(vals))

                # Delete custom moves that are no longer in the SO
                for line_id, move in existing_custom_by_line.items():
                    if line_id not in seen_line_ids:
                        list_commands.append(Command.delete(move.id))

            # 2. Handle Cylinder Move
            existing_cylinder_moves = cylinder_moves_by_production.get(production.id, self.env['stock.move'])
            linked_cylinder_moves = production.move_raw_ids.filtered(lambda m: m.is_cylinder_move)
            all_existing_cylinder = existing_cylinder_moves | linked_cylinder_moves

            if production.cylinder_id:
                raw_move_vals = production._get_move_raw_values(
                    production.cylinder_id,
                    production.product_qty,
                    production.cylinder_id.uom_id,
                )
                raw_move_vals['is_cylinder_move'] = True
                if production.partner_id:
                    raw_move_vals['restrict_partner_id'] = production.partner_id.id

                if all_existing_cylinder:
                    # Update or recreate if cylinder product changed
                    keep_move = all_existing_cylinder[0]
                    for extra_move in all_existing_cylinder[1:]:
                        list_commands.append(Command.delete(extra_move.id))

                    if keep_move.product_id != production.cylinder_id:
                        # Recreate to avoid product_id write restrictions
                        list_commands.append(Command.delete(keep_move.id))
                        list_commands.append(Command.create(raw_move_vals))
                    else:
                        update_vals = {}
                        if keep_move.product_uom_qty != production.product_qty:
                            update_vals['product_uom_qty'] = production.product_qty
                        if production.partner_id and keep_move.restrict_partner_id != production.partner_id:
                            update_vals['restrict_partner_id'] = production.partner_id.id
                        if update_vals:
                            list_commands.append(Command.update(keep_move.id, update_vals))
                        else:
                            if keep_move not in production.move_raw_ids:
                                list_commands.append(Command.link(keep_move.id))
                else:
                    # Create a new cylinder move
                    list_commands.append(Command.create(raw_move_vals))
            else:
                # Delete all cylinder moves
                if all_existing_cylinder:
                    list_commands.extend([Command.delete(m.id) for m in all_existing_cylinder])

            if list_commands:
                production.move_raw_ids = list_commands

    def write(self, vals):
        res = super(MrpProduction, self).write(vals)
        if 'partner_id' in vals:
            for production in self:
                if production.partner_id:
                    production.move_raw_ids.write({'restrict_partner_id': production.partner_id.id})
                    production.move_finished_ids.write({'restrict_partner_id': production.partner_id.id})
                    if production.picking_ids:
                        production.picking_ids.write({'owner_id': production.partner_id.id})

        if 'cylinder_id' in vals or 'product_qty' in vals or 'partner_id' in vals:
            for production in self:
                if production.state not in ('done', 'cancel'):
                    existing_moves = production.move_raw_ids.filtered(lambda m: m.is_cylinder_move)
                    if production.cylinder_id:
                        if existing_moves:
                            move_to_update = existing_moves[0]
                            if len(existing_moves) > 1:
                                existing_moves[1:].sudo()._action_cancel()
                                existing_moves[1:].sudo().unlink()

                            if move_to_update.product_id != production.cylinder_id:
                                move_to_update.sudo()._action_cancel()
                                move_to_update.sudo().unlink()

                                move_vals = production._get_move_raw_values(
                                    production.cylinder_id,
                                    production.product_qty,
                                    production.cylinder_id.uom_id,
                                )
                                move_vals['is_cylinder_move'] = True
                                if production.partner_id:
                                    move_vals['restrict_partner_id'] = production.partner_id.id
                                move = self.env['stock.move'].create(move_vals)
                                if production.state != 'draft':
                                    move._action_confirm()
                            else:
                                move_to_update.write({
                                    'product_uom_qty': production.product_qty,
                                    'restrict_partner_id': production.partner_id.id if production.partner_id else False,
                                })
                        else:
                            move_vals = production._get_move_raw_values(
                                production.cylinder_id,
                                production.product_qty,
                                production.cylinder_id.uom_id,
                            )
                            move_vals['is_cylinder_move'] = True
                            if production.partner_id:
                                move_vals['restrict_partner_id'] = production.partner_id.id
                            move = self.env['stock.move'].create(move_vals)
                            if production.state != 'draft':
                                move._action_confirm()
                    else:
                        if existing_moves:
                            existing_moves.sudo()._action_cancel()
                            existing_moves.sudo().unlink()
        return res

    def action_confirm(self):
        res = super(MrpProduction, self).action_confirm()
        for production in self:
            if production.cylinder_id:
                cylinder_move = production.move_raw_ids.filtered(lambda m: m.is_cylinder_move)
                if not cylinder_move:
                    move_vals = production._get_move_raw_values(
                        production.cylinder_id,
                        production.product_qty,
                        production.cylinder_id.uom_id,
                    )
                    move_vals['is_cylinder_move'] = True
                    if production.partner_id:
                        move_vals['restrict_partner_id'] = production.partner_id.id
                    move = self.env['stock.move'].create(move_vals)
                    move._action_confirm()
        return res

    def _get_moves_raw_values(self):
        res = super(MrpProduction, self)._get_moves_raw_values()
        for production in self:
            # 1. Add custom moves from Sale Order to expected moves list
            sale_order = False
            if production.sale_line_id:
                sale_order = production.sale_line_id.order_id
            elif production.origin:
                sale_order = self.env['sale.order'].search([('name', '=', production.origin)], limit=1)

            if sale_order:
                for line in sale_order.order_line:
                    if line.product_id == production.product_id:
                        continue
                    if line.display_type or not line.product_id:
                        continue
                    if line.product_id.type != 'consu':
                        continue

                    raw_move_vals = production._get_move_raw_values(
                        line.product_id,
                        line.product_uom_qty,
                        line.product_uom,
                    )
                    res.append(raw_move_vals)

            # 2. Add cylinder move to expected moves list
            if production.cylinder_id:
                raw_move_vals = production._get_move_raw_values(
                    production.cylinder_id,
                    production.product_qty,
                    production.cylinder_id.uom_id,
                )
                res.append(raw_move_vals)
        return res

