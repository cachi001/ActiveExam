"""Casos de uso del scoring y cierre de sesion (C-13).

Orquestan la consolidacion asincrona al cierre sobre los PUERTOS del dominio:
recomputan el score final desde los eventos persistidos (idempotente), liberan la
clave de sesion y deciden el encolado por umbral. El score PRIORIZA, NUNCA sanciona.
"""
