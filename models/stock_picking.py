# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class Picking(models.Model):
    _inherit = 'stock.picking'

    def _reset_sequence_if_needed(self):
        if self.env.context.get('skip_sequence_reset'):
            return
            
        for picking in self:
            if picking.name and picking.name != '/':
                sequence = picking.picking_type_id.sequence_id
                if sequence and sequence.number_next_actual > 1:
                    _logger.warning(">>> RESET SECUENCIA: devolviendo número para %s", picking.name)
                    # Restauramos la secuencia (devolvemos uno)
                    sequence.sudo().write({'number_next_actual': sequence.number_next_actual - 1})
                    #picking.name = '/'
                    _logger.warning(">>> OBTENIENDO NUEVO NOMBRE de secuencia para picking %s", picking.id)
                    new_name = self.env['ir.sequence'].next_by_code('seq_internal_picking')
                    
                    picking.name = new_name if new_name else sequence.next_by_id()
                    _logger.warning(">>> NAME RESETEADO a '/' para picking %s", picking.id)

    @api.model_create_multi
    def create(self, vals_list):
        _logger.warning(">>> ENTRANDO A stock.picking.create (PATCH RESET SEQUENCE)")
        pickings = super().create(vals_list)

        pickings._reset_sequence_if_needed()

        return pickings

    def write(self, vals):
        _logger.warning(">>> ENTRANDO A stock.picking.write (PATCH RESET SEQUENCE)")
        res = super().write(vals)
        self._reset_sequence_if_needed()
        return res

    def button_validate(self):
        _logger.warning(">>> ENTRANDO A stock.picking.button_validate")
        for picking in self:
            if picking.name == '/':
                sequence = picking.picking_type_id.sequence_id
                picking.name = sequence.next_by_id() if sequence else self.env['ir.sequence'].next_by_code('stock.picking')
                _logger.warning(">>> ASIGNANDO SECUENCIA FINAL: %s", picking.name)
        return super().button_validate()
