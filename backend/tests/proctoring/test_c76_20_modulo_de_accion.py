"""C-76 tarea 20.1/20.7 — fix del modulo SESIONES muerto en Auditoria.

`ModuloAuditoria.SESIONES` existia en el catalogo del filtro pero
`modulo_de_accion()` nunca lo devolvia (0 resultados siempre). Estas dos
acciones nuevas (eliminar sesion de test, archivar resultado) cierran el gap
via el prefijo "sesion.".

Pura (sin DB, sin asyncio) — mismo patron que test_audit_moodle_credencial_docente.py.
"""

from __future__ import annotations

from app.application.audit.acciones import AccionAuditoria, ModuloAuditoria, modulo_de_accion


def test_sesion_test_eliminada_resuelve_a_modulo_sesiones():
    assert modulo_de_accion(AccionAuditoria.SESION_TEST_ELIMINADA) == ModuloAuditoria.SESIONES


def test_resultado_archivar_resuelve_a_modulo_sesiones():
    assert modulo_de_accion(AccionAuditoria.RESULTADO_ARCHIVAR) == ModuloAuditoria.SESIONES


def test_prefijo_sesion_no_confunde_con_otros_modulos():
    """El prefijo "sesion." es NUEVO — no debe pisar ningun mapeo existente."""
    assert modulo_de_accion("user.create") == ModuloAuditoria.USUARIOS
    assert modulo_de_accion("examen.import") == ModuloAuditoria.EXAMENES


def test_modulo_sesiones_ya_no_es_un_filtro_muerto():
    """Antes de la tarea 20, NINGUNA accion resolvia a SESIONES — era un
    filtro que siempre daba 0 resultados en Auditoria. Ahora hay al menos una."""
    assert modulo_de_accion(AccionAuditoria.SESION_TEST_ELIMINADA) is not None
