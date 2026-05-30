"""Maquina de reintentos de la verificacion biometrica (PURA, RN-BIO-04, L2.5).

Hasta 2 REINTENTOS (3 intentos en total). Al 3.º fallo: el sistema SHALL generar
un evento critico y escalar a un proctor humano; SHALL NO abortar el examen ni
declarar automaticamente un veredicto de impostor (RN-BIO-04, RN-GLB-02, L2.5).

PUREZA (D1): maquina de estados sin efectos. La emision del evento critico y la
escalacion por la cola las hace la capa de aplicacion segun el VEREDICTO que esta
maquina produce; aqui solo se decide "queda reintento" vs "agotado -> escalar".
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

# Reintentos permitidos tras el primer intento (RN-BIO-04). 2 reintentos => 3
# intentos totales (intento 1 + 2 reintentos). No es secreto: regla de negocio.
MAX_REINTENTOS = 2
MAX_INTENTOS = MAX_REINTENTOS + 1


class VeredictoIntento(str, Enum):
    """Veredicto tras procesar un intento de verificacion."""

    VERIFICADO = "verificado"  # exito: la 1:1 re-inferida paso -> emitir clave
    REINTENTO_DISPONIBLE = "reintento_disponible"  # fallo, pero quedan intentos
    ESCALAR_A_PROCTOR = "escalar_a_proctor"  # se agotaron: evento critico + escalacion


class ReintentosAgotadosError(RuntimeError):
    """Se intento procesar un intento sobre una maquina ya escalada/verificada."""


@dataclass(frozen=True, slots=True)
class EstadoVerificacion:
    """Estado inmutable del proceso de verificacion de una sesion.

    ``intentos_fallidos`` cuenta los fallos acumulados. ``cerrado`` indica que ya
    se llego a un veredicto terminal (verificado o escalado); reabrirlo es un
    error de uso."""

    intentos_fallidos: int = 0
    cerrado: bool = False

    @classmethod
    def inicial(cls) -> EstadoVerificacion:
        return cls()

    @property
    def reintentos_restantes(self) -> int:
        """Reintentos que aun quedan disponibles (0 cuando se agotaron)."""
        return max(0, MAX_INTENTOS - self.intentos_fallidos - 1)

    def registrar_intento(self, *, exito: bool) -> tuple[EstadoVerificacion, VeredictoIntento]:
        """Procesa un intento y devuelve (nuevo_estado, veredicto).

        - exito -> VERIFICADO (estado cerrado): emitir clave de sesion.
        - fallo con intentos restantes -> REINTENTO_DISPONIBLE (estado abierto).
        - fallo que agota los intentos -> ESCALAR_A_PROCTOR (estado cerrado):
          evento critico + escalacion, SIN abortar ni sancionar (L2.5).
        """
        if self.cerrado:
            raise ReintentosAgotadosError(
                "verificacion ya cerrada (verificada o escalada)"
            )
        if exito:
            return replace(self, cerrado=True), VeredictoIntento.VERIFICADO
        fallidos = self.intentos_fallidos + 1
        if fallidos >= MAX_INTENTOS:
            return (
                replace(self, intentos_fallidos=fallidos, cerrado=True),
                VeredictoIntento.ESCALAR_A_PROCTOR,
            )
        return (
            replace(self, intentos_fallidos=fallidos),
            VeredictoIntento.REINTENTO_DISPONIBLE,
        )
