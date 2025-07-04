# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class Picking(models.Model):
    _inherit = 'stock.picking'

    def _is_real_outgoing(self):
        """True si es una salida real (no devolución)"""
        return self.picking_type_id.code == 'outgoing' and not self.return_id

    @api.model_create_multi
    def create(self, vals_list):
        _logger.warning(">>> ENTRANDO A stock.picking.create (PATCH SECUENCIA PERSONALIZADA)")
        pickings = super().create(vals_list)

        for picking in pickings:
            if not picking._is_real_outgoing():
                continue
            if picking.name and not picking.name.startswith('interno-'):
                sequence = picking.picking_type_id.sequence_id
                if sequence and sequence.number_next_actual > 1:
                    _logger.warning(">>> RESET SECUENCIA ORIGINAL: devolviendo número para %s", picking.name)
                    sequence.sudo().write({'number_next_actual': sequence.number_next_actual - 1})

                new_name = self.env['ir.sequence'].next_by_code('custom.picking.number')
                if not new_name:
                    raise UserError(_("La secuencia 'custom.picking.number' no está correctamente configurada."))
                
                picking.with_context(skip_sequence_reset=True).sudo().write({'name': new_name})
                _logger.warning(">>> NAME REASIGNADO a '%s' para picking %s", new_name, picking.id)

        return pickings

    def write(self, vals):
        _logger.warning(">>> ENTRANDO A stock.picking.write (PATCH SECUENCIA PERSONALIZADA)")
    
        if 'name' in vals and vals['name'] == '/':
            _logger.warning(">>> Se evita que se ponga name='/'")
            vals.pop('name')
    
        result = super().write(vals)
    
        if not self.env.context.get('skip_sequence_reset'):
            for picking in self:
                if not picking._is_real_outgoing():
                    continue
                # ⚠️ Si ya tiene secuencia oficial, no hacer nada más
                if picking.name and not picking.name.startswith('interno-') and '-' in picking.name:
                    _logger.warning(">>> El name ya tiene secuencia oficial (%s), no se cambia", picking.name)
                    continue
    
                # Si ya tiene secuencia personalizada interna, tampoco hacemos nada
                if picking.name and picking.name.startswith('interno-'):
                    _logger.warning(">>> El name ya tiene secuencia interna, no se cambia: %s", picking.name)
                    continue
    
                # Si llegamos hasta acá, reasignamos secuencia interna
                sequence = self.env['ir.sequence'].search([('code', '=', 'custom.picking.number')], limit=1)
                if sequence and sequence.number_next_actual > 1:
                    sequence.sudo().write({'number_next_actual': sequence.number_next_actual - 1})
                    _logger.warning(">>> SECUENCIA INTERNA devuelta un paso")
    
                new_name = self.env['ir.sequence'].next_by_code('custom.picking.number')
                if not new_name:
                    raise UserError(_("La secuencia 'custom.picking.number' no está correctamente configurada."))
    
                picking.with_context(skip_sequence_reset=True).sudo().write({'name': new_name})
                _logger.warning(">>> NAME REASIGNADO a '%s' para picking %s", new_name, picking.id)
    
        return result


    


    def button_validate(self):
        _logger.warning(">>> ENTRANDO A stock.picking.button_validate")
        result = super().button_validate()  # Ejecutamos la validación primero
    
        for picking in self:
            if picking._is_real_outgoing() and picking.name.startswith('interno-'):
                sequence = picking.picking_type_id.sequence_id
                if not sequence:
                    raise UserError(("No hay secuencia configurada para el tipo de picking: %s") % picking.picking_type_id.name)
    
                final_name = sequence.next_by_id()
                picking.with_context(skip_sequence_reset=True).sudo().write({'name': final_name})
                _logger.warning(">>> NAME FINAL al validar: %s", final_name)
    
        return result
