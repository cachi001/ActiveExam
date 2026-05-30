"""Errores de validacion de configuracion de examen (PURO, C-07).

El dominio expresa la invalidez de parametros como excepcion propia, sin acoplarse
a FastAPI; la presentacion la traduce a 422. ``InvalidExamConfigError`` lleva un
detalle por campo, util para el cuerpo del 422.
"""

from __future__ import annotations


class InvalidExamConfigError(ValueError):
    """Configuracion de examen invalida (-> 422). ``detalles`` mapea campo->motivo."""

    def __init__(self, detalles: dict[str, str]) -> None:
        self.detalles = detalles
        super().__init__("; ".join(f"{k}: {v}" for k, v in detalles.items()))
