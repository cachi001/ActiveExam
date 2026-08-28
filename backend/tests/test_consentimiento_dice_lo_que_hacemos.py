"""El consentimiento tiene que describir lo que el sistema hace de verdad.

El texto v1 afirmaba cosas del despliegue que no se cumplen: "infraestructura
self-hosted de la institución (soberanía de datos)" cuando corre en nube de
terceros, "evidencia cifrada at-rest en almacenamiento WORM" cuando la captura
vive en la base, y "el embedding se elimina al egreso" cuando esa purga no está
implementada.

Es la base legal del tratamiento de datos biométricos: prometer garantías
técnicas que no existen es peor que no mencionarlas. Decisión del dueño
(28/8/2026): el texto describe QUÉ se hace con los datos y qué derechos tiene el
alumno, y no habla de la infraestructura, que además puede cambiar sin que el
consentimiento tenga por qué enterarse.

Se pudo reescribir "v1" en lugar de emitir una v2 porque no había ni un
consentimiento firmado (verificado en producción y en desarrollo).
"""

from __future__ import annotations

import re

from app.domain.consent_flow.text_catalog import get_texto

# Palabras que describen infraestructura y no el tratamiento de los datos. Si
# alguna vuelve al texto, vuelve la promesa que no podemos sostener.
_INFRAESTRUCTURA = [
    "self-hosted",
    "soberania",
    "soberanía",
    "worm",
    "minio",
    "s3",
    "at-rest",
    "servidores propios",
]


def _texto_completo() -> str:
    t = get_texto("v1")
    return " ".join(t.bloques().values()).lower()


def test_no_promete_infraestructura():
    cuerpo = _texto_completo()
    encontradas = [p for p in _INFRAESTRUCTURA if p in cuerpo]
    assert not encontradas, f"el texto vuelve a hablar de infraestructura: {encontradas}"


def test_no_promete_una_purga_que_no_existe():
    """Ni la del embedding al egreso, ni un plazo de borrado automático.

    `purgar_capturas_vencidas` existe pero NO se dispara sola: el propio
    endpoint aclara que "no hay cron ni scheduler colgado de esto, lo llama
    explícitamente quien administra el sistema". Prometer que algo se elimina al
    vencer un plazo describe un automatismo que no existe.
    """
    cuerpo = _texto_completo()
    assert "egreso" not in cuerpo
    for promesa in ("se eliminan", "se elimina", "90 días", "vence ese plazo"):
        assert promesa not in cuerpo, f"promete un borrado que nadie ejecuta: {promesa!r}"


def test_sigue_diciendo_que_se_recolecta_biometria():
    """Sacar las promesas no puede terminar ocultando lo que sí se hace."""
    cuerpo = _texto_completo()
    assert "biométric" in cuerpo or "biometric" in cuerpo
    assert "cámara" in cuerpo


def test_avisa_que_se_capturan_imagenes_de_pantalla():
    assert "pantalla" in _texto_completo()


def test_mantiene_los_derechos_del_titular():
    """Ley 25.326: acceso, rectificación y supresión."""
    cuerpo = get_texto("v1").bloques()["derechos_titular"].lower()
    for derecho in ("acceso", "rectificaci", "supresi"):
        assert derecho in cuerpo


def test_dice_que_la_decision_la_toma_una_persona():
    """Regla dura #5: el sistema nunca sanciona solo."""
    cuerpo = _texto_completo()
    assert "una persona" in cuerpo or "humana" in cuerpo
    assert "nunca sanciona" in cuerpo


def test_esta_escrito_con_tildes():
    """Se le muestra tal cual al alumno: sin tildes se lee como un borrador."""
    cuerpo = _texto_completo()
    assert re.search(r"[áéíóú]", cuerpo), "el texto no tiene una sola tilde"
    # Las que estaban mal escritas en el original.
    for sin_tilde in ("biometricos", "senales", "sesion ", "eliminacion", "decision "):
        assert sin_tilde not in cuerpo, f"quedó sin tilde: {sin_tilde!r}"
