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

Segunda pasada (28/8/2026), tras verificar el texto contra el código:

  - Decía que se capturan "imágenes de tu pantalla". FALSO: no hay una sola
    llamada a `getDisplayMedia` en el front; todas las capturas son frames de la
    cámara (`captureVideoFrame` sobre el <video> de la webcam). De la pantalla se
    registran SEÑALES sin imagen (cambio de pestaña, pérdida de foco, monitor
    adicional, copiar/pegar "sin capturar contenido").
  - Decía que se guarda "desde dónde te conectaste". La sesión de proctoring no
    tiene columna de IP ni de ubicación; la IP solo queda en el audit log de tres
    acciones puntuales y, detrás del proxy de Render, es la del proxy.
  - No declaraba plazo. Ahora sí: 180 días para la IMAGEN, con purga automática
    (ver `programar_purga_capturas`). Decisión del dueño.
  - Los 24 meses de la biometría son VIGENCIA (hay que rehacer la captura), no
    conservación: la referencia anterior se marca no vigente, no se borra.
  - No se menciona ninguna ley: decisión del dueño.

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


def test_no_promete_que_se_borra_la_referencia_biometrica():
    """Los 24 meses son vigencia, NO conservación.

    `guardar_embedding_referencia` marca la referencia anterior como no vigente
    y crea una nueva: la vieja sigue en la base. Decir que "se elimina" a los 24
    meses (o al egreso) describiría un borrado que nadie ejecuta.
    """
    cuerpo = _texto_completo()
    assert "egreso" not in cuerpo
    for promesa in ("se elimina tu referencia", "se borra tu referencia"):
        assert promesa not in cuerpo, f"promete un borrado que nadie ejecuta: {promesa!r}"


def test_no_menciona_ninguna_ley():
    """Decisión del dueño: el texto describe lo que hacemos, no cita normativa."""
    cuerpo = _texto_completo()
    for cita in ("ley ", "25.326", "25326", "artículo", "articulo", "normativa"):
        assert cita not in cuerpo, f"el texto vuelve a citar normativa: {cita!r}"


def test_sigue_diciendo_que_se_recolecta_biometria():
    """Sacar las promesas no puede terminar ocultando lo que sí se hace."""
    cuerpo = _texto_completo()
    assert "biométric" in cuerpo or "biometric" in cuerpo
    assert "cámara" in cuerpo


def test_no_dice_que_se_capturan_imagenes_de_la_pantalla():
    """No existe `getDisplayMedia` en el front: la pantalla NO se captura.

    Las señales de pantalla (cambio de pestaña, foco, monitor adicional) sí se
    registran y el texto puede nombrarlas, pero como señales, nunca como imagen.
    """
    cuerpo = _texto_completo()
    for falsedad in (
        "imágenes de tu pantalla",
        "imagen de tu pantalla",
        "capturas de tu pantalla",
        "captura de tu pantalla",
        "graba tu pantalla",
        "grabación de tu pantalla",
    ):
        assert falsedad not in cuerpo, f"dice capturar la pantalla y no se captura: {falsedad!r}"


def test_avisa_que_se_registran_senales_del_navegador():
    """Sacar la falsedad de la pantalla no puede ocultar lo que sí se detecta."""
    cuerpo = _texto_completo()
    assert "pestaña" in cuerpo or "foco" in cuerpo or "ventana" in cuerpo


def test_no_dice_que_se_guarda_desde_donde_te_conectaste():
    """`proctoring_session` no tiene columna de IP ni de ubicación."""
    cuerpo = _texto_completo()
    for falsedad in ("desde dónde te conectaste", "desde donde te conectaste", "ubicación"):
        assert falsedad not in cuerpo, f"declara un dato que no se guarda: {falsedad!r}"


def test_declara_el_plazo_de_conservacion_de_la_imagen():
    """180 días, decisión del dueño, y con purga automática que lo hace cierto."""
    cuerpo = _texto_completo()
    assert "180 días" in cuerpo


def test_declara_la_vigencia_de_la_referencia_biometrica():
    """24 meses: al vencer hay que rehacer la captura."""
    cuerpo = _texto_completo()
    assert "24 meses" in cuerpo


def test_aclara_que_el_registro_del_examen_se_conserva():
    """La imagen se purga; el evento, su huella y la sesión NO.

    Decisión del dueño: son la prueba del examen. Prometer un borrado total
    sería mentir y además dejaría la evaluación indefendible ante un reclamo.
    """
    cuerpo = _texto_completo()
    assert "registro" in cuerpo
    assert "huella" in cuerpo or "hash" in cuerpo


def test_le_ofrece_ver_su_expediente_de_pruebas():
    """Decisión del dueño: lo que se le ofrece al alumno es VER, no reclamar.

    El expediente existe de verdad: `/alumno/informe/:sessionId`, alcanzable
    desde Mis notas cuando la nota fue anulada. Muestra decisión, motivo, señales
    y las capturas con su sello de integridad.
    """
    cuerpo = get_texto("v1").bloques()["derechos_titular"].lower()
    assert "expediente" in cuerpo
    assert "mis notas" in cuerpo


def test_no_lo_invita_a_reclamar_ni_a_impugnar():
    """Ofrecer un canal de reclamo que el sistema no tiene llevaba a que todos
    desestimaran la evaluación. Se muestra la prueba; el reclamo, si existe, es
    un procedimiento de la institución y no una promesa de esta pantalla."""
    cuerpo = _texto_completo()
    for invitacion in ("impugn", "reclam", "apel"):
        assert invitacion not in cuerpo, f"vuelve a invitar a reclamar: {invitacion!r}"


def test_avisa_que_la_evidencia_de_un_caso_abierto_no_se_borra():
    """El plazo tiene una excepción y el alumno tiene que conocerla: si su examen
    quedó anulado o sigue en revisión, las fotos se conservan."""
    cuerpo = get_texto("v1").bloques()["cuanto_tiempo"].lower()
    assert "anulado" in cuerpo
    assert "revisión" in cuerpo


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
