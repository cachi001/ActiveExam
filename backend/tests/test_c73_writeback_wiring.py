"""Contrato de cableado del write-back de Moodle (C-73 §7.2).

Clava la DECISIÓN de arranque que hasta ahora vivía inline en ``create_app``
(main_slim) sin ningún test: si ``MOODLE_BASE_URL`` está vacío, el write-back
queda DESHABILITADO (``build_writeback_svc`` devuelve ``None``) y la finalización
degrada de forma segura a ``persistir_nota_pendiente`` — la nota queda en estado
sincronizable y NINGÚN flujo se rompe. Con ``MOODLE_BASE_URL`` seteado, se
construye el servicio real y el token/curso/cm/component viajan al cliente.

Test puro: sin DB, sin red. Solo verifica la lógica de wiring.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.application.moodle.writeback_service import MoodleWritebackService
from app.infrastructure.moodle.wiring import build_moodle_config, build_writeback_svc


def _settings(**overrides):
    """Stand-in liviano de SlimSettings con los campos que lee el factory."""
    base = {
        "moodle_base_url": "",
        "moodle_ws_token": "",
        "moodle_component": "mod_assign",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_base_url_vacio_deshabilita_writeback():
    """Sin MOODLE_BASE_URL, el factory devuelve None (write-back deshabilitado)."""
    assert build_writeback_svc(_settings(moodle_base_url="")) is None


def test_base_url_seteado_construye_servicio():
    """Con MOODLE_BASE_URL, se construye el MoodleWritebackService real."""
    svc = build_writeback_svc(
        _settings(
            moodle_base_url="https://campustest.frm.utn.edu.ar",
            moodle_ws_token="tok",  # noqa: S106
        )
    )
    assert isinstance(svc, MoodleWritebackService)


def test_config_vacio_es_none():
    """build_moodle_config también degrada a None sin base_url (fuente única del gate)."""
    assert build_moodle_config(_settings(moodle_base_url="")) is None


def test_config_lleva_credencial_del_entorno_sin_destino():
    """El config lleva SOLO la credencial: URL, token y tipo de actividad.

    El curso y la actividad NO son configuracion institucional — son de cada examen.
    Tenerlos aca los convertia en un fallback silencioso hacia la libreta equivocada."""
    cfg = build_moodle_config(
        _settings(
            moodle_base_url="https://campustest.frm.utn.edu.ar",
            moodle_ws_token="tok_secreto",  # noqa: S106
            moodle_component="mod_quiz",
        )
    )
    assert cfg is not None
    assert cfg.base_url == "https://campustest.frm.utn.edu.ar"
    assert cfg.ws_token == "tok_secreto"  # noqa: S105
    assert cfg.component == "mod_quiz"
    assert not hasattr(cfg, "courseid")
    assert not hasattr(cfg, "cmid")
