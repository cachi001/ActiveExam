"""Contador en memoria de intentos fallidos de conexión a Moodle (C-73, seguridad).

Pura (sin DB): un dict en memoria del proceso, no una tabla. Avisa de un patrón
de "muchos intentos seguidos", no arma un historial forense — si el backend
reinicia, el contador vuelve a cero (trade-off aceptado a propósito).
"""

from __future__ import annotations

from app.application.moodle.intentos_fallidos_tracker import IntentosFallidosTracker


def test_por_debajo_del_umbral_no_dispara():
    t = IntentosFallidosTracker(umbral=5)
    for _ in range(4):
        assert t.registrar_fallo("docente-1") is False


def test_al_llegar_al_umbral_dispara():
    t = IntentosFallidosTracker(umbral=5)
    for _ in range(4):
        t.registrar_fallo("docente-1")
    assert t.registrar_fallo("docente-1") is True


def test_despues_de_disparar_el_contador_se_reinicia_y_vuelve_a_disparar():
    t = IntentosFallidosTracker(umbral=5)
    for _ in range(5):
        t.registrar_fallo("docente-1")  # dispara en el 5to
    for _ in range(4):
        assert t.registrar_fallo("docente-1") is False
    assert t.registrar_fallo("docente-1") is True


def test_resetear_borra_el_contador():
    t = IntentosFallidosTracker(umbral=5)
    for _ in range(4):
        t.registrar_fallo("docente-1")
    t.resetear("docente-1")
    for _ in range(4):
        assert t.registrar_fallo("docente-1") is False


def test_contadores_independientes_por_usuario():
    t = IntentosFallidosTracker(umbral=5)
    for _ in range(4):
        t.registrar_fallo("docente-1")
    assert t.registrar_fallo("docente-2") is False
