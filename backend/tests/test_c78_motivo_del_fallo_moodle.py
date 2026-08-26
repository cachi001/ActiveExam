"""c-78 — Cuando la nota no llega a Moodle, hay que poder saber POR QUÉ.

Encontrado el 26/8/2026 devolviendo notas al campus real. La sincronización
fallaba y todo lo que se podía ver era:

    {"enviadas": 0, "fallidas": 1, "sin_token": 0, "total": 1}

y en auditoría: *"0 enviada(s), 1 fallida(s) de 1"*. Nada más.

Moodle SÍ había explicado el motivo con todas las letras
(``User is not enrolled or does not have requested capability``), el backend lo
guardaba en ``error_detalle``... y no lo mostraba en ningún lado. Para
diagnosticarlo hubo que reproducir el write-back a mano contra la API del campus.

El día del examen eso no sirve: si las notas no llegan, el docente tiene que
poder ver el motivo en la pantalla, no adivinarlo.

Dos cosas, las dos necesarias:
  1. el motivo viaja en la fila del resultado, junto al estado
  2. la auditoría del lote resume los motivos, no solo el conteo

Y una regla que no se negocia: el motivo NUNCA puede incluir el token del
campus. El write-back ya lo redacta; acá se verifica que siga así.
"""

from __future__ import annotations

from app.application.moodle.sync_reporte import (
    redactar_secretos,
    resumen_de_motivos,
)


def test_el_resumen_dice_el_motivo_y_no_solo_el_conteo():
    motivos = ["User is not enrolled or does not have requested capability"]

    resumen = resumen_de_motivos(motivos)

    assert "not enrolled" in resumen


def test_agrupa_los_motivos_repetidos_en_vez_de_repetirlos_cien_veces():
    """Con 100 alumnos y una sola causa, el registro tiene que ser legible."""
    motivos = ["El alumno no está matriculado en el curso"] * 100

    resumen = resumen_de_motivos(motivos)

    assert resumen.count("El alumno no está matriculado") == 1
    assert "100" in resumen


def test_muestra_los_motivos_distintos_por_separado():
    motivos = ["sin credencial del docente"] * 3 + ["el alumno no existe en Moodle"] * 2

    resumen = resumen_de_motivos(motivos)

    assert "sin credencial del docente" in resumen
    assert "el alumno no existe en Moodle" in resumen
    assert "3" in resumen and "2" in resumen


def test_sin_motivos_no_inventa_texto():
    assert resumen_de_motivos([]) == ""


def test_corta_un_motivo_larguisimo():
    """Un stacktrace entero adentro del propósito de auditoría lo vuelve ilegible."""
    resumen = resumen_de_motivos(["x" * 5000])

    assert len(resumen) < 700


def test_el_token_del_campus_nunca_aparece_en_el_motivo():
    """Un token en el registro de auditoría es una credencial filtrada, y el
    audit log lo lee más gente que la que tiene el token."""
    texto = "falló con wstoken=abc123def456 al guardar la nota"

    limpio = redactar_secretos(texto, secretos=["abc123def456"])

    assert "abc123def456" not in limpio
    assert "[oculto]" in limpio


def test_redacta_aunque_el_secreto_venga_en_otra_capitalizacion():
    texto = "error con TOKEN=ABC123 en la llamada"

    limpio = redactar_secretos(texto, secretos=["abc123"])

    assert "ABC123" not in limpio


def test_sin_secretos_que_ocultar_deja_el_texto_igual():
    texto = "El alumno no está matriculado en el curso 7"

    assert redactar_secretos(texto, secretos=[]) == texto
    assert redactar_secretos(texto, secretos=[""]) == texto
