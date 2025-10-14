# -*- coding: utf-8 -*-
{
    # El nombre del módulo, corregido a "Sequence"
    "name": "Odoo Picking Sequence",
    "version": "17.0.1.0.0",

    # Una categoría más específica para facilitar la búsqueda
    "category": "Inventory/Warehouse Management",

    # Un resumen claro del propósito del módulo
    "summary": "Gestiona las secuencias de albaranes en dos pasos para evitar saltos y aumentar la flexibilidad.",

    # Una descripción detallada para la tienda de aplicaciones o para futuros desarrolladores
    "description": """
Este módulo modifica el comportamiento estándar de Odoo para la asignación de secuencias en albaranes de salida (remitos).

PROBLEMA RESUELTO:
Por defecto, Odoo asigna el número de secuencia final en el momento de la creación del albarán o al cambiar su tipo de operación, lo que provoca:
1.  Saltos (gaps) en las secuencias si un albarán se cancela.
2.  Poca flexibilidad en entregas parciales (backorders), donde puede ser necesario cambiar el tipo de operación (y por ende, el almacén de origen) antes de validar.

SOLUCIÓN IMPLEMENTADA:
1.  **Secuencia Interna Temporal:** Al crear un albarán de salida, se le asigna una secuencia temporal y genérica (ej: 'interno-XXXXX').
2.  **Flexibilidad de Edición:** Permite cambiar el Tipo de Operación en albaranes en curso (no validados) sin que esto consuma una secuencia oficial.
3.  **Secuencia Final en la Validación:** El número de secuencia definitivo, correspondiente al Tipo de Operación seleccionado, se asigna únicamente cuando el usuario hace clic en el botón 'Validar'.

BENEFICIOS:
-   Elimina los saltos en las secuencias de remitos.
-   Aumenta la flexibilidad operativa en la gestión de inventario.
-   Asegura un correlativo perfecto en los documentos oficiales.
    """,

    "author": 'Outsource',
    "maintainer": "Outsource", # Es buena práctica llenar también el maintainer
    "website": "", # Puedes añadir un sitio web si lo tienes

    "depends": ["stock"],
    "data": [
        # Vista necesaria para que el campo 'reading_picking_type' funcione
        "views/multiple_remittances_picking_views.xml",
        # Secuencia interna 'custom.picking.number'
        'data/ir_sequence_data.xml',
    ],
    "assets": {},
    "license": "LGPL-3",
    "installable": True,
    "auto_install": False,
    "application": True
}