# -*- coding: utf-8 -*-
from odoo import api,fields,models

class StockPicking(models.Model):
    _inherit = 'stock.picking'


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == '/':
                vals['name'] = '/'

        return super().create(vals_list) 
    
    def button_validate(self):
        for picking in self:
            if picking.name == '/':
                picking.name = picking.picking_type_id.sequence_id.next_by_id()

        return super().button_validate()

