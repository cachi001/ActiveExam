"""C-79 — fallback de `entidad` en el audit log, mismo mecanismo que
`modulo_de_accion` (C-76 tarea 20). Cierra la clase de bug encontrada en
Auditoria: un caller pasa `entidad_id` pero se olvida de `entidad`, y la fila
queda sin tipo — Auditoria no puede armar "Ver detalle" aunque el id esté.

Pura (sin DB, sin asyncio) — mismo patron que test_c76_20_modulo_de_accion.py.
"""

from __future__ import annotations

from app.application.audit.acciones import AccionAuditoria, EntidadAuditoria, entidad_de_accion


def test_comision_create_resuelve_a_entidad_comision():
    """El caso real que motivó el fallback: catalog_router pasaba entidad_id
    de la comisión pero no `entidad` — Auditoría no mostraba ningún botón."""
    assert entidad_de_accion(AccionAuditoria.COMISION_ALTA) == EntidadAuditoria.COMISION


def test_materia_acciones_resuelven_a_entidad_materia():
    assert entidad_de_accion(AccionAuditoria.MATERIA_ALTA) == EntidadAuditoria.MATERIA
    assert entidad_de_accion(AccionAuditoria.MATERIA_BAJA) == EntidadAuditoria.MATERIA


def test_examen_y_moodle_sync_resuelven_a_entidad_examen():
    assert entidad_de_accion(AccionAuditoria.EXAMEN_IMPORTACION) == EntidadAuditoria.EXAMEN
    assert entidad_de_accion("moodle.sync") == EntidadAuditoria.EXAMEN


def test_biometria_y_enrollment_resuelven_a_entidad_usuario():
    """El titular de una verificación/foto de referencia es el usuario dueño,
    no hay página de 'sesión de biometría' separada del perfil del alumno."""
    assert entidad_de_accion("biometria.verificacion") == EntidadAuditoria.USUARIO
    assert entidad_de_accion("enrollment.embedding_referencia.alta") == EntidadAuditoria.USUARIO


def test_dsr_resuelve_a_entidad_usuario():
    assert entidad_de_accion("dsr.access") == EntidadAuditoria.USUARIO
    assert entidad_de_accion("derecho_acceso.informe_devolucion") == EntidadAuditoria.USUARIO


def test_revision_y_sesion_resuelven_a_entidad_sesion():
    assert entidad_de_accion("review.decision.anulado") == EntidadAuditoria.SESION
    assert entidad_de_accion(AccionAuditoria.RESULTADO_ARCHIVAR) == EntidadAuditoria.SESION


def test_retention_session_deleted_no_resuelve_entidad():
    """La sesión YA NO EXISTE cuando se registra este evento (se borró por
    retención) — a propósito NO se clasifica como SESION: un "Ver detalle"
    llevaría a un 404. Cae al módulo Evidencia (listado general)."""
    assert entidad_de_accion("retention.session.deleted") is None


def test_sesion_test_eliminada_no_resuelve_entidad():
    """Mismo caso que retention.session.deleted: la sesión de diagnóstico ya
    no existe cuando se registra 'sesion.test.delete' — no debe clasificarse
    como SESION aunque comparta el prefijo 'sesion.' con RESULTADO_ARCHIVAR."""
    assert entidad_de_accion(AccionAuditoria.SESION_TEST_ELIMINADA) is None


def test_accion_desconocida_no_resuelve_entidad():
    assert entidad_de_accion("algo.que.no.existe") is None
    assert entidad_de_accion(None) is None
