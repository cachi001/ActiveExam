"""Reglas del flujo de consentimiento informado (PURO, C-08).

Base legal del tratamiento biometrico (Ley 25.326). Codifica como dominio puro,
SIN framework ni infraestructura (D1, test_architecture):

- ``errors``: errores de dominio del consentimiento (falta accion afirmativa, etc.).
- ``text_catalog``: versionado del texto de consentimiento (RN-CO-01) — el contenido
  legal deriva de C-01; aqui se versiona y se hashea para sellar la prueba.
- ``rules``: validacion de la accion afirmativa (RN-CO-02, server-side, D2), hash del
  texto exacto consentido (D1), y el gate de consentimiento previo a C-09 (D4).

C-08 NO redacta la politica legal (deriva de C-01) ni reabre el modelo de datos
(usa la entidad ``Consentimiento`` inmutable de C-05).
"""

from __future__ import annotations
