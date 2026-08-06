"""Helpers compartidos entre los routers de exam_content (C-69).

Gate de inscripción (staff vs alumno) y mapeo del resumen de examen al schema de
respuesta. Extraído de router.py al partir el god-file (2041 líneas) en sub-routers.
"""

from __future__ import annotations

from app.domain.auth.identity import AuthenticatedPrincipal
from app.presentation.api.v1.exam_content.schemas import ExamenContenidoResumenResponse

# Gate de inscripción (C-71): los roles de gestión ven TODO el catálogo/materias;
# el alumno ve solo lo de sus comisiones inscriptas.
_ROLES_STAFF = frozenset(
    {"admin_sistema", "admin_examenes", "proctor", "revisor", "coordinador", "auditor"}
)


def _es_staff(principal: AuthenticatedPrincipal) -> bool:
    return bool(set(principal.roles or []) & _ROLES_STAFF)


def _es_docente(principal: AuthenticatedPrincipal) -> bool:
    """True si el principal tiene el rol DOCENTE (gestión académica "de lo suyo").

    Bug real (verificación E2E de C-73): el docente NO es staff (ve TODO) ni
    alumno (ve solo sus inscripciones) — ve lo que DICTA (comision.docente_id).
    Sin esta rama, los 3 endpoints de listado (catálogo/materias/comisiones)
    caían al gate de inscripción del alumno y el docente veía siempre vacío.
    """
    return "tutor" in set(principal.roles or [])


def _resumen_to_response(r) -> ExamenContenidoResumenResponse:
    """Mapea un ExamenContenidoResumen de dominio al schema de respuesta (D3)."""
    return ExamenContenidoResumenResponse(
        id=r.id,
        titulo=r.titulo,
        cantidad_preguntas=r.cantidad_preguntas,
        comision_id=r.comision_id,
        comision_nombre=r.comision_nombre,
        materia_nombre=r.materia_nombre,
        apertura=r.apertura,
        cierre=r.cierre,
        tiempo_limite_min=r.tiempo_limite_min,
        intentos_permitidos=r.intentos_permitidos,
    )
