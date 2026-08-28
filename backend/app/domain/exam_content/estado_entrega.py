"""Dónde está una nota en su camino a la libreta del campus.

FUENTE ÚNICA. Antes esto vivía en cuatro lugares con nombres distintos: el enum
`WritebackEstado` (tres valores), dos constantes sueltas en `resultados_query`,
un diccionario de etiquetas en `stats/labels.py` y una copia propia en el export
con textos DIFERENTES. Así, la pantalla decía "Sin token" y el archivo "Sin
conexión al campus" para el mismo estado, y cuando apareció `manual` el badge lo
mostraba pero el filtro no lo ofrecía.

La etiqueta cuelga del enum a propósito, en vez de vivir en un diccionario
aparte: dos nombres para un concepto es exactamente lo que dejó divergir la
pantalla del archivo.

No es "el estado de Moodle": Moodle es el DESTINO, no el sujeto. Y tampoco es
aprobado/desaprobado, que es la otra cosa que se llama "estado de la nota".
"""

from __future__ import annotations

from enum import StrEnum


class EstadoEntregaNota(StrEnum):
    """Los cuatro estados que se PERSISTEN en `moodle_writeback_estado.estado`."""

    PENDIENTE = "pendiente"
    ENVIADO = "enviado"
    FALLIDO = "fallido"
    #: c-78 D14: alguien AFIRMA que cargó la nota en el campus a mano. No es
    #: `ENVIADO`: ahí el campus confirmó. La diferencia importa ante un reclamo
    #: por una nota que no aparece en la libreta.
    MANUAL = "manual"

    @property
    def etiqueta(self) -> str:
        """Lo que lee una persona, en pantalla Y en el archivo.

        Cortas a propósito: en el PDF la celda se recorta al ancho de su columna,
        y "Cargada (confirmada por el campus)" salía como "Cargada (confirma…" —
        un texto cortado a la mitad no dice menos, dice otra cosa.
        """
        return _ETIQUETA[self]

    @property
    def tono(self) -> str:
        """Color del badge. Vive acá y no en el frontend porque la distinción
        entre "el campus lo confirmó" y "alguien dice que la cargó" es semántica,
        no estética: si la elige cada pantalla, cada pantalla la elige distinto.
        """
        return _TONO[self]


#: DERIVADO, nunca persistido: no hay credencial del campus para mandar la nota.
#: Es una condición del sistema en un momento, no un estado de la nota —
#: guardarlo dejaría mil filas diciendo "sin token" el día después de configurar
#: el campus. Se calcula al mostrar y se apaga solo.
#:
#: Va fuera del enum justamente para que no se pueda escribir en la base por
#: accidente.
ESTADO_SIN_TOKEN = "sin_token"

#: El NOMBRE del estado, no una frase. El porqué va aparte, como motivo: una
#: columna de estado que dice "Falta conectar el campus" no está diciendo en qué
#: estado está la entrega, está diciendo por qué no avanzó.
_ETIQUETA: dict[EstadoEntregaNota, str] = {
    EstadoEntregaNota.PENDIENTE: "Pendiente",
    EstadoEntregaNota.ENVIADO: "Enviado",
    EstadoEntregaNota.FALLIDO: "Fallido",
    EstadoEntregaNota.MANUAL: "Cargada a mano",
}

_TONO: dict[EstadoEntregaNota, str] = {
    EstadoEntregaNota.PENDIENTE: "warning",
    EstadoEntregaNota.ENVIADO: "success",
    EstadoEntregaNota.FALLIDO: "error",
    EstadoEntregaNota.MANUAL: "primary",
}

#: "Sin token" es el nombre de la variable, no algo que decirle a un docente: lo
#: que necesita saber es qué le falta hacer.
ETIQUETA_SIN_TOKEN = "Falta conectar el campus"
TONO_SIN_TOKEN = "error"


def etiqueta_estado_entrega(estado: str) -> str:
    """Etiqueta legible de un estado, incluido el derivado `sin_token`."""
    if estado == ESTADO_SIN_TOKEN:
        return ETIQUETA_SIN_TOKEN
    try:
        return EstadoEntregaNota(estado).etiqueta
    except ValueError:
        return estado


def tono_estado_entrega(estado: str) -> str:
    if estado == ESTADO_SIN_TOKEN:
        return TONO_SIN_TOKEN
    try:
        return EstadoEntregaNota(estado).tono
    except ValueError:
        return "neutral"


#: Lo que consume la UI para armar el filtro y el badge, en orden. Incluye el
#: derivado: el docente tiene que poder FILTRAR por "falta conectar el campus",
#: que es el estado en el que más notas se le pueden quedar trabadas.
def estados_para_ui() -> list[dict[str, str]]:
    estados = [
        {"valor": e.value, "etiqueta": e.etiqueta, "tono": e.tono} for e in EstadoEntregaNota
    ]
    estados.insert(
        3,
        {
            "valor": ESTADO_SIN_TOKEN,
            "etiqueta": ETIQUETA_SIN_TOKEN,
            "tono": TONO_SIN_TOKEN,
        },
    )
    return estados
