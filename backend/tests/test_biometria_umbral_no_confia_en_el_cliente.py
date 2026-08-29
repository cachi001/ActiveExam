"""La verificación biométrica 1:1 tenía dos agujeros que la volvían decorativa.

Reportado por el dueño el 29/8/2026: **otra persona pasó la verificación con 89%
de coincidencia** y el sistema la dio por válida.

## Bug 1 — el umbral estaba ~4x demasiado permisivo

El descriptor lo produce face-api.js (128-d, real: se verificó el guardado en la
base — norma 1.393, valores entre -0.41 y 0.459). face-api está calibrado para
distancia EUCLIDIANA y su umbral documentado para "misma persona" es **0.60**.

El sistema comparaba por distancia COSENO con umbral 0.35, que no es lo mismo.
Convertido con la norma real (``d_euclid² = 2·n²·d_coseno``):

| criterio                  | coseno | euclidiana |
|---------------------------|--------|------------|
| umbral que había          | 0.35   | **1.165**  |
| estándar de face-api      | 0.093  | 0.60       |
| el impostor que pasó      | 0.11   | 0.653      |

El modelo había detectado bien que era otra persona (0.653 > 0.60). El umbral la
dejó pasar igual. Decisión del dueño: usar el estándar de face-api.

## Bug 2 — el umbral lo mandaba el CLIENTE

`POST /proctoring/biometria/verificar-referencia` aceptaba `umbral` en el body y
lo obedecía. Verificado contra la API real: un vector ALEATORIO (ni siquiera una
cara) con ``umbral: 999`` devolvía ``es_match: true``. Bypass completo de la
identidad sin siquiera aparecer frente a la cámara.

Viola la regla dura #6 (cliente = sensor no confiable). El umbral es una decisión
de seguridad del servidor; el cliente no opina.

El campo se sigue ACEPTANDO en el body (para no romper con un 422 a los clientes
ya desplegados, que mandan `umbral: null`), pero se IGNORA.
"""

from __future__ import annotations

import math

import pytest

from app.domain.biometrics.matching import (
    UMBRAL_COSENO_DEFECTO,
    comparar_identidad,
)

#: Norma típica de un descriptor de face-api (la medida en la base fue 1.393).
_NORMA = 1.393


def _coseno_desde_euclidiana(d_euclid: float, norma: float = _NORMA) -> float:
    """Convierte una distancia euclidiana a coseno para vectores de esa norma."""
    return (d_euclid**2) / (2 * norma**2)


# ---------------------------------------------------------------------------
# Bug 1: el umbral
# ---------------------------------------------------------------------------


def test_el_umbral_equivale_al_estandar_de_face_api():
    """0.60 euclidiana es el corte con el que face-api fue calibrado."""
    esperado = _coseno_desde_euclidiana(0.60)
    assert UMBRAL_COSENO_DEFECTO == pytest.approx(esperado, abs=0.005)


def test_el_umbral_ya_no_acepta_al_impostor_reportado():
    """La medición real del caso: 0.11 de coseno (0.653 euclidiana)."""
    assert 0.11 > UMBRAL_COSENO_DEFECTO


def test_sigue_aceptando_a_la_persona_correcta():
    """El dueño midió 0.03 de coseno (~0.34 euclidiana) contra su propia
    referencia. Endurecer el umbral no puede dejar afuera al legítimo."""
    assert 0.03 < UMBRAL_COSENO_DEFECTO


def test_un_vector_al_azar_no_es_match():
    """Un embedding que no es una cara queda lejísimos de cualquier referencia."""
    import random

    random.seed(7)
    aleatorio = [random.uniform(-0.4, 0.4) for _ in range(128)]
    referencia = [math.sin(i) * 0.3 for i in range(128)]
    assert comparar_identidad(aleatorio, referencia).es_match is False


# ---------------------------------------------------------------------------
# Bug 2: el umbral lo decide el SERVIDOR
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_el_cliente_no_puede_aflojar_el_umbral():
    """Un `umbral` gigante en el body no debe volver match a un impostor.

    Antes devolvía ``es_match: true`` con un vector aleatorio y ``umbral: 999``.
    """
    from app.application.biometrics.verificar_referencia_vigente import (
        VerificarReferenciaVigenteService,
    )

    import random

    random.seed(7)
    vivo = [random.uniform(-0.4, 0.4) for _ in range(128)]
    referencia = [math.sin(i) * 0.3 for i in range(128)]

    class _RepoFalso:
        """Devuelve la referencia ya descifrada (no es un mock de DB: el servicio
        acá no toca la base, solo compara — ver regla dura #4)."""

    servicio = VerificarReferenciaVigenteService.__new__(
        VerificarReferenciaVigenteService
    )
    # Se ejercita la resolución del umbral, que es donde estaba el agujero.
    assert servicio._umbral_efectivo(999.0) == UMBRAL_COSENO_DEFECTO
    assert servicio._umbral_efectivo(None) == UMBRAL_COSENO_DEFECTO
    assert servicio._umbral_efectivo(0.0001) == UMBRAL_COSENO_DEFECTO
    # Y con el umbral del servidor, el impostor no pasa.
    assert comparar_identidad(vivo, referencia, umbral=UMBRAL_COSENO_DEFECTO).es_match is False
