"""Entidades de dominio (PURAS).

Modelan las 8 entidades transaccionales del modelo de datos (`04`): Usuario,
Examen, Sesion, Asignacion, Consentimiento, Embedding, Evidencia y Caso
disciplinario, mas el Evento y la entrada de Audit log. Sin SQLAlchemy ni
infraestructura (regla dura monorepo-scaffolding / D1): el mapeo a la base vive
en ``app.infrastructure.persistence.models``.
"""
