"""Gate del liveness hibrido (PURO, RN-BIO-05, DD-18).

El liveness es PRERREQUISITO OBLIGATORIO de la comparacion 1:1: sin un liveness
exitoso, la 1:1 NO se ejecuta (RN-BIO-05). El liveness es HIBRIDO:
- pasivo: parpadeo natural involuntario, micro-movimientos, profundidad 3D
  estimada por la geometria de los landmarks de Face Mesh.
- activo: 1-2 RETOS ALEATORIOS que el estudiante debe completar (girar cabeza,
  parpadear a demanda, etc.), para elevar el costo de un ataque ensayado.

PUREZA (D1): este modulo NO calcula los landmarks (eso es el motor de vision en
el cliente / la re-inferencia server-side); modela el GATE: dada la evidencia de
liveness (senales pasivas + retos resueltos), decide si el liveness es exitoso.
La deteccion de camara virtual se modela como una SENAL adicional que, si esta
presente, invalida el liveness (es una de las capas de defensa, DD-18).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum

# Catalogo de retos activos posibles (RN-BIO-05). El cliente elige 1-2 al azar; el
# backend re-verifica que los reportados pertenezcan a este catalogo y se hayan
# resuelto. No es un secreto: es el vocabulario de retos del dominio.


class RetoActivo(str, Enum):
    """Retos activos aleatorios del liveness hibrido (DD-18)."""

    GIRAR_IZQUIERDA = "girar_izquierda"
    GIRAR_DERECHA = "girar_derecha"
    PARPADEAR = "parpadear"
    ACERCARSE = "acercarse"
    SONREIR = "sonreir"


CATALOGO_RETOS: frozenset[RetoActivo] = frozenset(RetoActivo)

# Cantidad de retos activos exigidos por intento (1-2, DD-18).
MIN_RETOS_ACTIVOS = 1
MAX_RETOS_ACTIVOS = 2


@dataclass(frozen=True, slots=True)
class SenalesPasivas:
    """Senales del analisis pasivo de liveness (calculadas por el motor de vision).

    Son booleanos del veredicto pasivo: el motor (cliente + re-inferencia) provee
    si detecto parpadeo involuntario, micro-movimientos y profundidad 3D coherente
    con un rostro real (no una foto plana)."""

    parpadeo_detectado: bool
    micro_movimientos: bool
    profundidad_3d_coherente: bool

    @property
    def pasivo_ok(self) -> bool:
        """El pasivo pasa solo si las TRES senales son positivas (defensa estricta)."""
        return (
            self.parpadeo_detectado
            and self.micro_movimientos
            and self.profundidad_3d_coherente
        )


@dataclass(frozen=True, slots=True)
class EvidenciaLiveness:
    """Evidencia de liveness de un intento: pasivo + retos resueltos + integridad.

    ``camara_virtual_detectada`` es la senal de la heuristica de integridad del
    cliente (DD-18): si es ``True``, el liveness se invalida (capa de defensa)."""

    pasivas: SenalesPasivas
    retos_solicitados: tuple[RetoActivo, ...]
    retos_resueltos: tuple[RetoActivo, ...] = field(default_factory=tuple)
    camara_virtual_detectada: bool = False


class LivenessInvalidoError(ValueError):
    """La evidencia de liveness esta mal formada (retos fuera de catalogo, cantidad)."""


def validar_retos_solicitados(retos: Sequence[RetoActivo]) -> None:
    """Valida que la cantidad de retos sea 1-2 y todos esten en el catalogo."""
    if not (MIN_RETOS_ACTIVOS <= len(retos) <= MAX_RETOS_ACTIVOS):
        raise LivenessInvalidoError(
            f"se exigen entre {MIN_RETOS_ACTIVOS} y {MAX_RETOS_ACTIVOS} retos activos"
        )
    fuera = [r for r in retos if r not in CATALOGO_RETOS]
    if fuera:
        raise LivenessInvalidoError(f"retos fuera de catalogo: {fuera}")


def liveness_exitoso(evidencia: EvidenciaLiveness) -> bool:
    """Decide si el liveness hibrido es exitoso (gate obligatorio, RN-BIO-05).

    Exito sii: (1) no se detecto camara virtual, (2) el pasivo paso, y (3) TODOS
    los retos activos solicitados fueron resueltos. Si falta cualquiera, el
    liveness NO es exitoso y la comparacion 1:1 NO debe ejecutarse."""
    validar_retos_solicitados(evidencia.retos_solicitados)
    if evidencia.camara_virtual_detectada:
        return False
    if not evidencia.pasivas.pasivo_ok:
        return False
    resueltos = set(evidencia.retos_resueltos)
    return all(reto in resueltos for reto in evidencia.retos_solicitados)
