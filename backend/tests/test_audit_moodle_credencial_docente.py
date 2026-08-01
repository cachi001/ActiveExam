"""Fix: la credencial personal de Moodle del docente quedaba con `modulo=NULL`
en Auditoría (C-73 §13).

`_auditar_credencial` (config/router.py) usaba `accion="moodle_credencial_update"`
sin pasar `modulo=` explícito, y `modulo_de_accion()` solo reconocía
`"moodle.sync"` (con punto) — nunca ese string con guion bajo. Resultado: esas
filas no aparecían filtrando por módulo "MOODLE" en la pantalla de Auditoría.

Separación deliberada de "Configuración → Campus Moodle" (institucional,
`modulo=CONFIGURACION`): la credencial PERSONAL del docente es `modulo=MOODLE` +
`entidad=USUARIO` — filtrando por módulo quedan sin ambigüedad.

Pura (sin DB) — `modulo_de_accion` es una función determinista.
"""

from __future__ import annotations

from app.application.audit.acciones import AccionAuditoria, ModuloAuditoria, modulo_de_accion


def test_el_string_viejo_moodle_credencial_update_no_tenia_modulo():
    """Documenta el bug tal cual estaba: guion bajo, no reconocido por el fallback.

    NO se corrige este string (quedan históricas sin módulo, C-73 §13.5) — se
    reemplaza por acciones nuevas con punto, que sí matchean."""
    assert modulo_de_accion("moodle_credencial_update") is None


def test_conectar_desconectar_renovar_resuelven_a_modulo_moodle():
    assert modulo_de_accion(AccionAuditoria.MOODLE_CREDENCIAL_CONECTAR) == ModuloAuditoria.MOODLE
    assert (
        modulo_de_accion(AccionAuditoria.MOODLE_CREDENCIAL_DESCONECTAR) == ModuloAuditoria.MOODLE
    )
    assert modulo_de_accion(AccionAuditoria.MOODLE_CREDENCIAL_RENOVAR) == ModuloAuditoria.MOODLE


def test_no_se_confunde_con_moodle_sync():
    """`moodle.sync` (institucional/admin, C-69) sigue resolviendo a MOODLE
    también — no es que dejen de convivir, es que la personal del docente
    ahora TAMBIÉN cae ahí en vez de a ningún lado."""
    assert modulo_de_accion("moodle.sync") == ModuloAuditoria.MOODLE
