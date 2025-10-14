# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class Picking(models.Model):
    _inherit = 'stock.picking'
    reading_picking_type = fields.Boolean(compute="_compute_reading_picking_type")
    
    @api.depends('state', 'name')
    def _compute_hide_picking_type(self):
        """
        SOBRESCRITURA NATIVA: Controla el atributo 'readonly' del campo 'picking_type_id'.

        Propósito: Permitir la edición del "Tipo de Operación" en albaranes que ya
        no están en estado 'borrador', pero que usan nuestra secuencia interna temporal.
        Esto es crucial para los backorders, que se crean en estados avanzados ('En espera', 'Listo').

        Lógica:
        1.  Ejecuta la lógica original de Odoo.
        2.  Luego, verifica si el albarán tiene un nombre que comienza con 'interno-'.
        3.  Si es así y aún no está 'hecho' o 'cancelado', fuerza el campo a ser editable
            (hide_picking_type = False), anulando la restricción de Odoo.
        """
        super()._compute_hide_picking_type()
        for picking in self:
            is_internal_remit = picking.name and picking.name.startswith('interno-')
            is_in_progress = picking.state not in ('done', 'cancel')
            if is_internal_remit and is_in_progress:
                picking.hide_picking_type = False

            
    @api.depends('state')
    def _compute_reading_picking_type(self):
        """
        Método de cómputo para el campo 'reading_picking_type'.

        Este campo parece ser un auxiliar para controlar atributos en la vista XML,
        posiblemente para lógica más compleja que el simple readonly. La lógica actual
        se basa en el estado y si el albarán proviene de una venta.
        """
        for picking in self:
            is_not_draft_or_cancel = picking.state in ('draft')
            # Condición 2: ¿El estado NO es borrador ni cancelado?
            for lines in picking.move_ids_without_package:
                if lines.sale_line_id:
                    is_not_draft_or_cancel = picking.state not in ('draft','cancel','done')
                    break
                else:
                    is_not_draft_or_cancel = picking.state  in ('draft')
            # Pasamos ambas condiciones y devolvemos su resultado negado de verdad
            picking.reading_picking_type = not(is_not_draft_or_cancel)

    def _is_real_outgoing(self):
        """
        Método de ayuda para identificar albaranes de salida que no son devoluciones.
        Filtra la lógica para que solo aplique a los remitos de venta.
        """
        return self.picking_type_id.code == 'outgoing' and not self.return_id

    # ==============================================================================
    # PASO 1: CREACIÓN PROACTIVA DE LA SECUENCIA INTERNA
    # ==============================================================================
    @api.model_create_multi
    def create(self, vals_list):
        """
        SOBRESCRITURA NATIVA: Asigna la secuencia interna al crear albaranes.

        Propósito: Ser proactivo y asignar nuestro número de secuencia temporal ('interno-XXXX')
        desde el momento de la creación, tanto para el albarán original como para los backorders.

        Lógica:
        1.  Itera sobre la lista de valores de los albaranes a crear.
        2.  Verifica si es un albarán de salida ('outgoing').
        3.  Si lo es, y no tiene un nombre asignado, obtiene el siguiente número de la
            secuencia 'custom.picking.number' y lo inyecta en los valores.
        4.  Finalmente, llama al `create` original con los valores ya modificados.
        """
        for vals in vals_list:
            picking_type_id = vals.get('picking_type_id')
            if picking_type_id:
                picking_type = self.env['stock.picking.type'].browse(picking_type_id)
                if picking_type.code == 'outgoing' and (not vals.get('name') or vals.get('name') == '/'):
                    new_name = self.env['ir.sequence'].next_by_code('custom.picking.number')
                    if not new_name:
                        raise UserError(_("La secuencia para remitos internos ('custom.picking.number') no está definida."))
                    vals['name'] = new_name
                    _logger.info(f"CREATE: Asignando secuencia interna proactiva: {new_name}")
        return super().create(vals_list)

    # ==============================================================================
    # PASO 2: WRITE CON BYPASS Y CORRECCIÓN ROBUSTA (VERSIÓN FINAL)
    # ==============================================================================
    def write(self, vals):
        """
            SOBRESCRITURA NATIVA: Gestiona el cambio de 'picking_type_id' en albaranes existentes.
    
            Propósito: Evitar el error de Odoo que prohíbe cambiar el tipo de operación fuera
            del estado 'borrador' y prevenir que se consuma una secuencia oficial al guardar.
    
            Estrategia "Bypass y Corrección":
            1.  Identifica los albaranes que usan la secuencia interna y no están en borrador.
            2.  **Bypass:** Los pone temporalmente en estado 'borrador' para engañar la validación nativa.
            3.  **Actuar:** Llama al `write` original, que ahora se ejecuta sin error pero consume
                la nueva secuencia y cambia el nombre como efecto secundario.
            4.  **Corrección:** Inmediatamente después, revierte los efectos secundarios:
                a. "Devuelve" el número a la secuencia oficial decrementando su 'próximo número'.
                b. Restaura el nombre 'interno-' original y el estado original del albarán.
        """
        
        if 'picking_type_id' not in vals or self.env.context.get('skip_write_fix'):
            return super().write(vals)

        # Preparamos los datos para los albaranes que necesitan el bypass
        bypass_data = {}
        for picking in self:
            if picking.name and picking.name.startswith('interno-') and picking.state != 'draft':
                bypass_data[picking.id] = {'old_name': picking.name, 'original_state': picking.state}

        # Si hay albaranes que necesitan el bypass, los ponemos en estado 'draft'
        if bypass_data:
            pickings_to_bypass = self.browse(bypass_data.keys())
            # Usamos write del ORM, es más seguro que SQL directo para esta operación
            super(Picking, pickings_to_bypass).write({'state': 'draft'})

        # Llamamos al super() original para TODOS los albaranes del recordset
        # Dejamos que haga el cambio de tipo de operación y reasigne la secuencia
        res = super().write(vals)

        # Ahora, corregimos SOLO los que estaban en nuestro bypass_data
        if bypass_data:
            for picking in self.browse(bypass_data.keys()):
                # Verificamos si Odoo efectivamente cambió el nombre
                if picking.name != bypass_data[picking.id]['old_name']:
                    _logger.warning(f"WRITE DETECTED: Odoo cambió el nombre a {picking.name}. Revirtiendo.")
                    
                    # Identificamos el tipo de operación que se acaba de asignar en el super()
                    new_picking_type = picking.picking_type_id
                    sequence_to_fix = new_picking_type.sequence_id

                    if sequence_to_fix:
                        # Devolvemos el número consumido por error
                        current_next = sequence_to_fix.number_next_actual
                        sequence_to_fix.sudo().write({'number_next_actual': current_next - 1})
                        _logger.info(f"SECUENCIA CORREGIDA: Devuelto número a '{sequence_to_fix.name}'.")

                # Restauramos el nombre y el estado original usando un write con contexto de bypass
                # Esto es la parte más crítica y robusta
                picking.with_context(skip_write_fix=True).write({
                    'name': bypass_data[picking.id]['old_name'],
                    'state': bypass_data[picking.id]['original_state']
                })

        return res


    


    def button_validate(self):
        """
        SOBRESCRITURA NATIVA: Asigna la secuencia final y definitiva.

        Propósito: Es el paso final del flujo. Justo antes o después de la validación,
        reemplaza el nombre 'interno-XXXX' por el número de secuencia oficial que
        corresponde al 'Tipo de Operación' finalmente seleccionado.

        Lógica:
        1.  Ejecuta la validación original de Odoo (mueve el stock, cambia estado a 'hecho').
        2.  Itera sobre los albaranes que se están validando.
        3.  Si un albarán es una salida real y tiene el nombre interno:
            a. Obtiene la secuencia del 'picking_type_id' actual.
            b. Consume el siguiente número de esa secuencia.
            c. Actualiza el nombre del albarán con este número final.
        """
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
