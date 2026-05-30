"""Casos de uso del consentimiento informado (aplicacion, C-08).

Orquestan el dominio del flujo de consentimiento (``consent_flow``) con la entidad
inmutable ``Consentimiento`` (C-05), el audit log (append-only) para la eleccion de
via alternativa, y la cola de mensajeria para la escalacion al proctor. No reabren
el modelo de datos (C-05) ni redactan la politica legal (deriva de C-01).
"""

from __future__ import annotations
