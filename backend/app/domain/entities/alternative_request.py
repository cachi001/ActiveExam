"""Entidad de dominio: solicitud de via alternativa (C-63).

Representa el ciclo de vida mutable de la eleccion de via alternativa:
  pendiente_coordinador  -> el alumno eligio la via; ningun coordinador la habilito aun.
  habilitado_por_coordinador -> un coordinador/admin habilito la solicitud; el alumno puede rendir.

Esta entidad es MUTABLE (el estado cambia) — por eso vive en una tabla propia
y NO en el audit log (que es append-only e inmutable, DD-13).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class EstadoViaAlternativa(str, enum.Enum):
    """Estado de la solicitud de via alternativa (D-02)."""

    PENDIENTE_COORDINADOR = "pendiente_coordinador"
    HABILITADO_POR_COORDINADOR = "habilitado_por_coordinador"


@dataclass(frozen=True, slots=True)
class SolicitudViaAlternativa:
    """Solicitud de via alternativa — entidad de dominio (frozen, C-63 D-01).

    Campos:
      id                 : UUID de la solicitud (str).
      user_id            : username del alumno.
      exam_id            : id del examen, o ``"perfil"`` para enrollment (sentinel D-08).
      estado             : estado actual de la solicitud.
      timestamp_solicitud: ISO-8601 UTC del momento del pedido del alumno.
      timestamp_habilitacion: ISO-8601 UTC de cuando el coordinador habilito (None si pendiente).
      habilitado_por     : username del coordinador que habilito (None si pendiente).
    """

    id: str
    user_id: str
    exam_id: str
    estado: EstadoViaAlternativa
    timestamp_solicitud: str
    timestamp_habilitacion: str | None
    habilitado_por: str | None
