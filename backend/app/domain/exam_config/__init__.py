"""Reglas de configuracion de examen de DOMINIO (PURO, C-07).

Codifica las reglas de negocio RN-EX que validan la configuracion de un examen,
SIN framework ni infraestructura (D1, test_architecture):

- ``catalog``: catalogo CANONICO de detectores conocidos (MediaPipe, KB 11) — un
  detector fuera del catalogo es invalido (RN-EX-01).
- ``validation``: coherencia de la ventana temporal (fin > inicio), rango del
  umbral de score, detectores en catalogo y politica de retencion valida (RN-EX-01,
  D4). Devuelve errores de dominio que la presentacion mapea a 422.

C-07 NO reabre el modelo de datos (C-05): estas reglas operan sobre la entidad
``Examen`` existente; la lista de habilitados y la referencia se modelan como
estructura dentro de sus campos JSONB (parametros), sin migracion nueva.
"""

from __future__ import annotations
