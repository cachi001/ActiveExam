"""Helpers compartidos entre los routers de exam_content (C-69).

Gate de inscripción (staff vs alumno) y mapeo del resumen de examen al schema de
respuesta. Extraído de router.py al partir el god-file (2041 líneas) en sub-routers.
"""

from __future__ import annotations

from app.domain.auth.identity import AuthenticatedPrincipal
from app.presentation.api.v1.exam_content.schemas import ExamenContenidoResumenResponse

# Gate de inscripción (C-71): los roles de gestión ven TODO el catálogo/materias;
# el alumno ve solo lo de sus comisiones inscriptas.
# c-79: "coordinador" SALE de este set — dejó de tener alcance global (antes veía
# TODO como staff, lo mismo que admin). Queda acotado a SUS materias asignadas
# (materia_coordinador, N:M), igual que el tutor a sus comisiones — ver
# `_es_coordinador` abajo. Solo admin_sistema conserva alcance global.
_ROLES_STAFF = frozenset({"admin_sistema"})

# Baja lógica del catálogo (c-78 D1). Misma forma tri-estado que `GET /users?estado=`:
# 'activo' (default, eliminado_en IS NULL) | 'inactivo' (solo dados de baja) | 'todos'.
ESTADOS_CATALOGO_VALIDOS = frozenset({"activo", "inactivo", "todos"})


def _es_staff(principal: AuthenticatedPrincipal) -> bool:
    return bool(set(principal.roles or []) & _ROLES_STAFF)


def _es_docente(principal: AuthenticatedPrincipal) -> bool:
    """True si el principal tiene el rol TUTOR (gestión académica "de lo suyo").

    Bug real (verificación E2E de C-73): el tutor NO es staff (ve TODO) ni
    alumno (ve solo sus inscripciones) — ve lo que DICTA (comision_tutor, N:M
    desde c-79). Sin esta rama, los 3 endpoints de listado (catálogo/materias/
    comisiones) caían al gate de inscripción del alumno y el tutor veía siempre
    vacío.
    """
    return "tutor" in set(principal.roles or [])


def _es_coordinador(principal: AuthenticatedPrincipal) -> bool:
    """True si el principal tiene el rol COORDINADOR (c-79: acotado por materia,
    ya NO es staff). Ve lo que coordina (materia_coordinador, N:M)."""
    return "coordinador" in set(principal.roles or [])


def _es_profesor(principal: AuthenticatedPrincipal) -> bool:
    """True si el principal tiene el rol PROFESOR (c-78: acotado por materia).

    Ve lo de SUS materias (``materia_profesor``, N:M), igual que el coordinador
    con las que coordina. Lo que NO tiene, y es lo que lo distingue, es el
    veredicto de integridad (`revisar_sesion`) — ver D11."""
    return "profesor" in set(principal.roles or [])


def _resumen_to_response(r) -> ExamenContenidoResumenResponse:
    """Mapea un ExamenContenidoResumen de dominio al schema de respuesta (D3)."""
    return ExamenContenidoResumenResponse(
        id=r.id,
        titulo=r.titulo,
        cantidad_preguntas=r.cantidad_preguntas,
        comision_id=r.comision_id,
        comision_nombre=r.comision_nombre,
        comision_codigo=r.comision_codigo,
        materia_id=getattr(r, "materia_id", None),
        materia_nombre=r.materia_nombre,
        materia_codigo=r.materia_codigo,
        apertura=r.apertura,
        cierre=r.cierre,
        tiempo_limite_min=r.tiempo_limite_min,
        intentos_permitidos=r.intentos_permitidos,
        eliminado_en=getattr(r, "eliminado_en", None),
        borrador=getattr(r, "borrador", False),
        modo_preguntas=getattr(r, "modo_preguntas", "fijo"),
    )
