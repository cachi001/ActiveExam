"""Proctoring backend application package.

Arquitectura Clean/Hexagonal pragmatica (DD - `08` Patrones). Capas:

- ``domain``: entidades, reglas y scoring. PURO: sin imports de framework
  ni de adaptadores de ``infrastructure``.
- ``application``: casos de uso (orquestan dominio + puertos).
- ``infrastructure``: adaptadores concretos detras de puertos
  (``persistence``, ``messaging``, ``storage``, ``auth``).
- ``presentation``: routers FastAPI + handlers WS/SSE + healthchecks.
- ``workers``: procesos asincronos (re-inferencia, firma, reportes).
- ``observability``: metricas, trazas y logging estructurado.

Este es el scaffolding de C-04. Las entidades de dominio llegan en C-05;
auth real en C-06. Aqui solo vive el esqueleto.
"""
