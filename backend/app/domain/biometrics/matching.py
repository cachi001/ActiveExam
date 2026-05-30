"""Comparacion biometrica 1:1 por distancia coseno (PURA, RN-BIO-01/02/03).

La verificacion de identidad compara el embedding capturado contra el embedding
de REFERENCIA (cargado en C-07, leido cifrado de la DB) mediante distancia
coseno. El umbral es CONSERVADOR (RN-BIO-03, D3): rechazar a un legitimo es peor
que aceptar a un impostor en este paso, porque la verificacion silenciosa
continua (US-005) y la revision humana son la red de seguridad.

PUREZA (D1): solo aritmetica sobre secuencias de floats; sin numpy ni cripto. El
descifrado del embedding de referencia lo hace infraestructura (KMS) ANTES de
llegar aqui; este modulo NUNCA ve ciphertext ni claves.

Distancia coseno usada: ``1 - cos_sim``, en [0, 2]. Dos vectores identicos -> 0
(match perfecto); ortogonales -> 1; opuestos -> 2. ``match`` es ``distancia <
umbral`` (estricto: en el umbral exacto NO es match, RN-BIO-03 conservador).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

# Umbral conservador por DEFECTO de la distancia coseno (RN-BIO-03). El valor
# operativo definitivo lo fija la configuracion del examen (C-07); aqui se
# documenta un default razonable para vectores faciales normalizados. NO es un
# secreto: es un parametro de negocio.
UMBRAL_COSENO_DEFECTO = 0.35


class EmbeddingInvalidoError(ValueError):
    """El embedding no es comparable (vacio, dimension distinta o norma cero)."""


@dataclass(frozen=True, slots=True)
class ResultadoComparacion:
    """Resultado de una comparacion 1:1 (distancia + veredicto contra el umbral)."""

    distancia: float
    umbral: float

    @property
    def es_match(self) -> bool:
        """``True`` si la distancia es ESTRICTAMENTE menor que el umbral (RN-BIO-03)."""
        return self.distancia < self.umbral


def distancia_coseno(a: Sequence[float], b: Sequence[float]) -> float:
    """Distancia coseno ``1 - cos_sim`` entre dos vectores no nulos.

    Levanta ``EmbeddingInvalidoError`` si los vectores estan vacios, tienen
    dimension distinta o norma cero (no comparables)."""
    if not a or not b:
        raise EmbeddingInvalidoError("embedding vacio: no comparable")
    if len(a) != len(b):
        raise EmbeddingInvalidoError(
            f"dimensiones distintas: {len(a)} vs {len(b)}"
        )
    producto = sum(x * y for x, y in zip(a, b, strict=True))
    norma_a = math.sqrt(sum(x * x for x in a))
    norma_b = math.sqrt(sum(y * y for y in b))
    if norma_a == 0.0 or norma_b == 0.0:
        raise EmbeddingInvalidoError("norma cero: no comparable")
    cos_sim = producto / (norma_a * norma_b)
    # Acota por errores de punto flotante fuera de [-1, 1].
    cos_sim = max(-1.0, min(1.0, cos_sim))
    return 1.0 - cos_sim


def comparar_identidad(
    capturado: Sequence[float],
    referencia: Sequence[float],
    *,
    umbral: float = UMBRAL_COSENO_DEFECTO,
) -> ResultadoComparacion:
    """Compara 1:1 el embedding capturado contra el de referencia (RN-BIO-01).

    Devuelve la distancia coseno y el veredicto contra el ``umbral`` conservador.
    NO decide habilitacion ni emite clave: eso es responsabilidad de la capa de
    aplicacion (separacion de concerns)."""
    if umbral <= 0.0:
        raise EmbeddingInvalidoError("umbral debe ser > 0")
    distancia = distancia_coseno(capturado, referencia)
    return ResultadoComparacion(distancia=distancia, umbral=umbral)
