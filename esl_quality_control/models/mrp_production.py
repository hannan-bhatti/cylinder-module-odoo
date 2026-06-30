# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.exceptions import UserError

class MrpProduction(models.Model):
    _inherit = "mrp.production"

    check_ids = fields.One2many('quality.check', 'production_id', 'Checks')
    quality_check_todo = fields.Boolean('Pending checks', compute='_compute_check', search='_search_quality_check_todo')
    quality_check_fail = fields.Boolean(compute='_compute_check')
    quality_alert_ids = fields.One2many('quality.alert', 'production_id', 'Alerts')
    quality_alert_count = fields.Integer(compute='_compute_quality_alert_count')

    def _compute_check(self):
        for production in self:
            todo = False
            fail = False
            checks = production.check_ids
            checks.fetch(['quality_state'])
            for check in checks:
                if check.quality_state == 'none':
                    todo = True
                elif check.quality_state == 'fail':
                    fail = True
                if fail and todo:
                    break
            production.quality_check_fail = fail
            production.quality_check_todo = todo

    def _search_quality_check_todo(self, operator, value):
        if operator != 'in':
            return NotImplemented

        domain = [('production_id', '!=', False), ('quality_state', '=', 'none')]
        query_check_production = self.env['quality.check']._search(domain)
        return [('id', 'in', query_check_production.subselect('production_id'))]

    def _compute_quality_alert_count(self):
        for production in self:
            production.quality_alert_count = len(production.quality_alert_ids)

    def _create_quality_checks(self):
        for production in self:
            # 1. Operation-level quality checks
            operation_points_domain = self.env['quality.point']._get_domain(production.product_id, production.picking_type_id, measure_on='operation')
            existing_operation_points = production.check_ids.filtered(lambda c: c.measure_on == 'operation').point_id.ids
            if existing_operation_points:
                operation_points_domain += [('id', 'not in', existing_operation_points)]
            operation_points = self.env['quality.point'].sudo().search(operation_points_domain)
            
            check_vals_list = []
            for point in operation_points:
                if point.check_execute_now():
                    check_vals_list.append({
                        'point_id': point.id,
                        'team_id': point.team_id.id,
                        'measure_on': 'operation',
                        'production_id': production.id,
                        'company_id': production.company_id.id,
                    })

            # 2. Product-level quality checks
            product_points_domain = self.env['quality.point']._get_domain(production.product_id, production.picking_type_id, measure_on='product')
            product_points = self.env['quality.point'].sudo().search(product_points_domain)
            if product_points:
                product_check_vals = product_points._get_checks_values(production.product_id, production.company_id.id, existing_checks=production.sudo().check_ids)
                for val in product_check_vals:
                    val.update({
                        'production_id': production.id,
                    })
                check_vals_list += product_check_vals
            
            if check_vals_list:
                self.env['quality.check'].sudo().create(check_vals_list)

    def action_confirm(self):
        res = super(MrpProduction, self).action_confirm()
        self._create_quality_checks()
        return res

    def action_cancel(self):
        res = super(MrpProduction, self).action_cancel()
        self.sudo().mapped('check_ids').filtered(lambda x: x.quality_state == 'none').unlink()
        return res

    def button_mark_done(self):
        self.ensure_one()
        checks = self.check_ids.filtered(lambda c: c.quality_state == 'none')
        if checks:
            return checks.action_open_quality_check_wizard()
        return super(MrpProduction, self).button_mark_done()

    def check_quality(self):
        self.ensure_one()
        checks = self.check_ids.filtered(lambda c: c.quality_state == 'none')
        if checks:
            return checks.action_open_quality_check_wizard()
        return True

    def action_open_quality_check_production(self):
        action = self.env["ir.actions.actions"]._for_xml_id("esl_quality_control.quality_check_action_picking")
        action['context'] = self.env.context.copy()
        action['context'].update({
            'search_default_production_id': [self.id],
            'default_production_id': self.id,
        })
        return action

    def action_open_on_demand_quality_check(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("esl_quality_control.quality_check_action_main")
        action['views'] = [(False, 'form')]
        action['context'] = {
            **self.env.context,
            'default_product_id': self.product_id.id,
            'default_production_id': self.id,
        }
        return action

    def button_quality_alert(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("esl_quality_control.quality_alert_action_check")
        action['views'] = [(False, 'form')]
        action['context'] = {
            'default_product_id': self.product_id.id,
            'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
            'default_production_id': self.id,
        }
        return action

    def open_quality_alert_production(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("esl_quality_control.quality_alert_action_check")
        action['context'] = {
            'default_product_id': self.product_id.id,
            'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
            'default_production_id': self.id,
        }
        action['domain'] = [('id', 'in', self.quality_alert_ids.ids)]
        action['views'] = [(False, 'list'), (False, 'form')]
        if len(self.quality_alert_ids) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = self.quality_alert_ids.id
        return action
