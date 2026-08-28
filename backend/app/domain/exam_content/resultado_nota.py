"""El resultado académico de una nota: aprobado, desaprobado o anulada.

FUENTE ÚNICA. Antes esto no era un enum: eran `if` encadenados escritos DOS
veces, uno en el frontend (`veredictoNota`) y otro en el export (`_veredicto`).
Y ya habían divergido — la copia de Python no conocía la anulación, así que una
nota anulada por fraude salía "Aprobado" en el Excel mientras la pantalla decía
"Anulada".

Es distinto del estado de la ENTREGA (`estado_entrega.py`), que dice si la nota
llegó a la libreta del campus. Uno habla de la nota, el otro de su viaje.

Se DERIVA, no se persiste: sale de comparar la nota contra la nota de aprobación
del examen, más el veredicto humano si lo hubo. Guardarlo obligaría a recalcular
todas las filas cada vez que alguien corrige la nota de aprobación.
"""

from __future__ import annotations

from enum import StrEnum

from app.domain.exam_content.estado_entrega import ETIQUETA_SIN_TOKEN

#: Motivo de retención que CAMBIA el resultado. La anulación es una decisión
#: humana que deja la nota efectiva en 0: el número calculado ya no vale.
RETENCION_ANULADA = "anulada"

#: Todavía no hay veredicto humano: el resultado no es definitivo.
RETENCION_EN_RIESGO = "en_riesgo"

#: Lo que vale una nota anulada. No es "sin nota": el alumno rindió y hubo un
#: veredicto.
NOTA_DE_UNA_ANULACION = 0.0


class ResultadoNota(StrEnum):
    APROBADO = "aprobado"
    DESAPROBADO = "desaprobado"
    #: Anulada por fraude (decisión humana, D11b).
    ANULADA = "anulada"
    #: Superó el umbral de riesgo y todavía nadie decidió. El resultado NO es
    #: definitivo: un revisor todavía puede anularlo. Decir "Aprobado" sobre algo
    #: que puede darse vuelta es afirmar de más — la nota igual se muestra en su
    #: columna, así que el número no se esconde, sólo deja de leerse como firme.
    EN_REVISION = "en_revision"
    #: Todavía no hay nota. NO es un desaprobado: meter en el mismo bolsón a
    #: quien sacó 3 y a quien no rindió infla un número que se informa.
    SIN_NOTA = "sin_nota"
    #: Hay nota, pero el examen no define con cuánto se aprueba. Decir
    #: "desaprobado" sería una afirmación que nadie hizo.
    SIN_CRITERIO = "sin_criterio"

    @property
    def etiqueta(self) -> str:
        return _ETIQUETA[self]

    @property
    def tono(self) -> str:
        return _TONO[self]


_ETIQUETA: dict[ResultadoNota, str] = {
    ResultadoNota.APROBADO: "Aprobado",
    ResultadoNota.DESAPROBADO: "Desaprobado",
    ResultadoNota.ANULADA: "Anulada",
    ResultadoNota.EN_REVISION: "En revisión",
    ResultadoNota.SIN_NOTA: "Sin nota",
    ResultadoNota.SIN_CRITERIO: "Sin criterio de aprobación",
}

#: `critico` y no `error` para la anulación: desaprobar es un resultado
#: académico normal, y una nota anulada por fraude es una decisión disciplinaria.
#: Pintarlas del mismo rojo las iguala, y no son lo mismo.
_TONO: dict[ResultadoNota, str] = {
    ResultadoNota.APROBADO: "success",
    ResultadoNota.DESAPROBADO: "error",
    ResultadoNota.ANULADA: "critico",
    ResultadoNota.EN_REVISION: "warning",
    ResultadoNota.SIN_NOTA: "neutral",
    ResultadoNota.SIN_CRITERIO: "neutral",
}


def resultado_de(
    *, aprobado: bool | None, nota: float | None, retenido_por: str | None
) -> ResultadoNota:
    """El resultado de una fila, en un solo lugar.

    ``aprobado`` viene calculado contra la nota de aprobación del examen; es
    ``None`` cuando falta la nota o el examen no tiene criterio cargado.
    """
    if retenido_por == RETENCION_ANULADA:
        return ResultadoNota.ANULADA
    if retenido_por == RETENCION_EN_RIESGO:
        return ResultadoNota.EN_REVISION
    if aprobado is True:
        return ResultadoNota.APROBADO
    if aprobado is False:
        return ResultadoNota.DESAPROBADO
    if nota is None:
        return ResultadoNota.SIN_NOTA
    return ResultadoNota.SIN_CRITERIO


def nota_efectiva(*, nota: float | None, retenido_por: str | None) -> float | None:
    """La nota que VALE, que no siempre es la calculada.

    Una anulación la deja en 0. La calculada se sigue mandando aparte para poder
    mostrarla ("la nota calculada era 78"): el dato no se pierde, sólo deja de
    ser el que manda.
    """
    if retenido_por == RETENCION_ANULADA:
        return NOTA_DE_UNA_ANULACION
    return nota


def resultados_para_ui() -> list[dict[str, str]]:
    """Lo que consume la pantalla para pintar el chip. Sin esto tendría que
    repetir los textos y los colores, que es como se desincronizaron antes."""
    return [
        {"valor": r.value, "etiqueta": r.etiqueta, "tono": r.tono} for r in ResultadoNota
    ]


def etiqueta_resultado(valor: str) -> str:
    """Etiqueta legible de un resultado. Vacío si no se reconoce el valor."""
    try:
        return ResultadoNota(valor).etiqueta
    except ValueError:
        return ""


# ---------------------------------------------------------------------------
# Por qué la nota NO se entrega al campus.
#
# Estas etiquetas vivían escritas a mano en el frontend (`RETENCION_CONFIG` de
# EstadoBadge.tsx). El texto que ve una persona es una decisión de dominio, no
# de la pantalla: si lo elige cada pantalla, cada pantalla lo dice distinto —
# que es exactamente lo que pasó entre la tabla y el archivo.
# ---------------------------------------------------------------------------

#: Motivos que le pasan al EXAMEN o a la COMISIÓN, no a la nota de una persona.
#: Se avisan UNA vez arriba de la tabla, no en cada fila: si al examen le falta
#: el destino, le falta para los 40 alumnos, y verlo 40 veces no agrega nada.
MOTIVOS_DEL_EXAMEN = frozenset({"sin_destino", "sin_credencial_docente"})

#: valor -> (etiqueta corta para el chip, tono, explicación completa)
_RETENCION: dict[str, tuple[str, str, str]] = {
    "en_riesgo": (
        "En revisión",
        # Naranja y no rojo: el rojo es para lo que salió mal. Una nota en
        # revisión no salió mal, está esperando que una persona la mire.
        "warning",
        "La sesión superó el umbral de riesgo y todavía no la revisó una "
        "persona. La nota no se envía hasta que haya decisión.",
    ),
    "anulada": (
        "Anulada",
        # Más fuerte que un error común: es una decisión disciplinaria.
        "critico",
        "El examen fue anulado por decisión humana. La nota que queda es 0.",
    ),
    "sin_destino": (
        "Falta el destino",
        "error",
        "Este examen no tiene cargado el curso y la actividad de Moodle donde "
        "va la nota. Configuralos en el examen (sección «Destino en Moodle») y "
        "volvé a sincronizar.",
    ),
    "no_rindio": (
        "No rindió",
        # Neutral: no es una falla del sistema ni algo que el docente tenga que
        # destrabar. Es un hecho del alumno.
        "neutral",
        "El alumno está inscripto en la comisión y no se presentó a rendir. La "
        "nota es 0 por ausente, no por haber rendido mal.",
    ),
    "sin_credencial_docente": (
        # El MISMO texto que el estado `sin_token`, importado y no repetido:
        # dicen lo mismo (falta la credencial del campus) y escribirlo dos veces
        # es como divergen. El candado de `test_estados_moodle_fuente_unica` lo
        # agarró apenas lo dupliqué.
        ETIQUETA_SIN_TOKEN,
        "error",
        "La nota se devuelve al campus con la cuenta del tutor a cargo de la "
        "comisión, para que en la libreta figure quién la puso. Falta que esa "
        "comisión tenga tutor asignado y que esa persona conecte su cuenta en "
        "Configuración → Campus (Moodle). Apenas la conecte, volvé a sincronizar.",
    ),
}

#: Lo que se muestra cuando el motivo no está mapeado. Nunca el código crudo.
RETENCION_DESCONOCIDA = (
    "Retenida por revisión",
    "error",
    "La nota no se entrega hasta que se resuelva la revisión.",
)


def etiqueta_retencion(motivo: str | None) -> str:
    """Etiqueta corta del motivo, o vacío si no hay retención."""
    if not motivo:
        return ""
    return _RETENCION.get(motivo, RETENCION_DESCONOCIDA)[0]


def retenciones_para_ui() -> list[dict[str, str]]:
    """Lo que consume la pantalla para pintar una fila retenida.

    ``alcance`` dice dónde mostrarlo: ``sesion`` va en la fila (es de esa
    persona), ``examen`` va sólo en el aviso de arriba (le pasa a todos).
    """
    return [
        {
            "valor": valor,
            "etiqueta": etiqueta,
            "tono": tono,
            "detalle": detalle,
            "alcance": "examen" if valor in MOTIVOS_DEL_EXAMEN else "sesion",
        }
        for valor, (etiqueta, tono, detalle) in _RETENCION.items()
    ]
