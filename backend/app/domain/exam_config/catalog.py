"""Catalogo CANONICO de detectores conocidos (PURO, C-07, KB 11).

Los tres detectores de MediaPipe del MVP (KB 11 §Los tres detectores). Un examen
solo puede activar detectores de este catalogo (RN-EX-01); cualquier otro es un
parametro invalido (-> 422). El catalogo vive en dominio porque es una regla de
negocio (que se puede monitorear), no un detalle de infraestructura.

C-07 solo persiste QUE detectores estan activos y sus umbrales; las reglas de
transicion de cada detector son scope de C-11 (no aqui).
"""

from __future__ import annotations

import enum


class Detector(str, enum.Enum):
    """Detector de vision conocido (catalogo del MVP, KB 11)."""

    FACE_DETECTION = "face_detection"  # BlazeFace: ausencia / multiples rostros
    FACE_MESH = "face_mesh"            # 468 landmarks: mirada + embedding continuo
    POSE = "pose"                      # postura corporal


DETECTORES_CONOCIDOS: frozenset[str] = frozenset(d.value for d in Detector)

# Rango permitido del umbral de score (proporcion 0..1; conservador por defecto,
# RN-SC-05). Fuera de rango -> 422.
UMBRAL_SCORE_MIN: float = 0.0
UMBRAL_SCORE_MAX: float = 1.0

# Politicas de retencion validas (RN-EX-01 / retencion C-19). El detalle de los
# holds/plazos lo aplica C-19; aqui solo se restringe a un conjunto valido.
POLITICAS_RETENCION: frozenset[str] = frozenset(
    {"estandar", "extendida", "minima"}
)


def es_detector_conocido(nombre: str) -> bool:
    """``True`` si el detector pertenece al catalogo canonico."""
    return nombre in DETECTORES_CONOCIDOS
