"""Entidad de dominio Sesion: el ciclo de vida central del examen proctorizado.

PURA (regla dura monorepo-scaffolding / D1): sin SQLAlchemy ni infraestructura.
Modela el estado de la Sesion como un enum del dominio y las transiciones
validas de su maquina de estados. La invariante a nivel de MOTOR (la base
rechaza un estado fuera del enum) la garantiza la migracion 002 con un CHECK; la
maquina de estados de aqui evita transiciones invalidas en la capa de dominio.

Estados (`04` Sesion): iniciada -> activa -> {finalizada | flaggeada} -> cerrada.
``cerrada`` es terminal. ``flaggeada`` indica revision humana pendiente (L2.5: el
sistema flaggea, no sanciona).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum


class EstadoSesion(str, Enum):
    """Estados del ciclo de vida de la Sesion (enum del dominio, `04` Sesion)."""

    INICIADA = "iniciada"
    ACTIVA = "activa"
    FINALIZADA = "finalizada"
    FLAGGEADA = "flaggeada"
    CERRADA = "cerrada"


# Transiciones validas de la maquina de estados. Una Sesion arranca ``iniciada``,
# pasa a ``activa``, puede ``flaggearse`` (revision humana) o ``finalizar``, y
# termina ``cerrada`` (estado terminal, sin salida).
_TRANSICIONES: dict[EstadoSesion, frozenset[EstadoSesion]] = {
    EstadoSesion.INICIADA: frozenset({EstadoSesion.ACTIVA, EstadoSesion.CERRADA}),
    EstadoSesion.ACTIVA: frozenset(
        {EstadoSesion.FLAGGEADA, EstadoSesion.FINALIZADA, EstadoSesion.CERRADA}
    ),
    EstadoSesion.FLAGGEADA: frozenset(
        {EstadoSesion.FINALIZADA, EstadoSesion.CERRADA}
    ),
    # Tras finalizar, la consolidacion asincrona del score (C-13) decide: flaggear
    # para revision humana (cola C-16) o archivar (cerrada). La decision es de
    # PRIORIZACION, nunca una sancion (L2.5).
    EstadoSesion.FINALIZADA: frozenset(
        {EstadoSesion.FLAGGEADA, EstadoSesion.CERRADA}
    ),
    EstadoSesion.CERRADA: frozenset(),  # terminal
}


@dataclass(frozen=True, slots=True)
class Sesion:
    """Sesion de examen (entidad central). Inmutable: las transiciones devuelven
    una nueva instancia (estilo value-object), preservando la trazabilidad."""

    user_id: str
    exam_id: str
    clave_sesion: str
    estado: EstadoSesion = EstadoSesion.INICIADA
    score: float | None = None
    id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def crear(cls, *, user_id: str, exam_id: str, clave_sesion: str) -> Sesion:
        """Crea una Sesion en estado ``iniciada`` (punto de entrada del ciclo)."""
        return cls(user_id=user_id, exam_id=exam_id, clave_sesion=clave_sesion)

    def transicionar(self, destino: EstadoSesion) -> Sesion:
        """Devuelve una nueva Sesion en ``destino`` si la transicion es valida.

        Lanza ``ValueError`` si ``destino`` no es alcanzable desde el estado
        actual segun la maquina de estados del dominio.
        """
        permitidos = _TRANSICIONES[self.estado]
        if destino not in permitidos:
            raise ValueError(
                f"transicion invalida: {self.estado.value} -> {destino.value}"
            )
        return self._con_estado(destino)

    def _con_estado(self, estado: EstadoSesion) -> Sesion:
        """Helper interno: copia la Sesion fijando ``estado`` (sin validar)."""
        return replace(self, estado=estado)
