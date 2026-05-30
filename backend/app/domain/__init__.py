"""Capa de dominio (PURA).

REGLA DURA (monorepo-scaffolding / D1): este paquete y todos sus submodulos
NO deben importar FastAPI, SQLAlchemy, Pydantic-Settings, ni ningun adaptador
de ``app.infrastructure``. El dominio depende solo de la libreria estandar y,
a lo sumo, de Pydantic para value objects sin side-effects.

Las entidades de negocio (sesiones, eventos, evidencia, scoring) son scope de
C-05 y posteriores. En C-04 este paquete queda intencionalmente vacio.
"""
