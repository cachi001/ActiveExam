"""Cómo se cuenta lo que pasó al devolver notas a Moodle (c-78).

EL PROBLEMA QUE CIERRA: la sincronización fallaba y lo único visible era
``0 enviada(s), 1 fallida(s) de 1``. Moodle había explicado el motivo con todas
las letras (``User is not enrolled or does not have requested capability``), el
backend lo guardaba en ``error_detalle``, y no se mostraba en ningún lado. Para
diagnosticarlo hubo que reproducir el write-back a mano contra la API del campus.

El día del examen eso no sirve: si las notas no llegan, el docente tiene que ver
el motivo en la pantalla.

Dos cuidados que no son opcionales:

- **Agrupar.** Con 100 alumnos y una sola causa, repetir el mismo texto cien
  veces vuelve el registro ilegible. Se cuenta cuántas veces pasó cada motivo.
- **No filtrar el token.** El audit log lo lee más gente que la que tiene la
  credencial del campus: un token ahí adentro es una credencial filtrada.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

# Tope del resumen dentro del propósito de auditoría. Un stacktrace entero lo
# vuelve ilegible; con esto entran varias causas distintas y sus conteos.
_MAX_RESUMEN = 600
# Tope por motivo, para que uno larguísimo no se coma el lugar de los demás.
_MAX_MOTIVO = 180


def resumen_de_motivos(motivos: Iterable[str]) -> str:
    """Agrupa los motivos de fallo y los cuenta, del más frecuente al menos.

    Devuelve "" si no hay motivos: no se inventa texto para decir que no pasó
    nada.
    """
    limpios = [(m or "").strip() for m in motivos]
    limpios = [m[:_MAX_MOTIVO] for m in limpios if m]
    if not limpios:
        return ""

    partes = [
        f"{motivo} (x{veces})" if veces > 1 else motivo
        for motivo, veces in Counter(limpios).most_common()
    ]
    resumen = "; ".join(partes)
    if len(resumen) > _MAX_RESUMEN:
        resumen = resumen[: _MAX_RESUMEN - 1] + "…"
    return resumen


def redactar_secretos(texto: str, *, secretos: Iterable[str]) -> str:
    """Reemplaza cualquier secreto que haya quedado en el texto por ``[oculto]``.

    Compara sin distinguir mayúsculas: el mismo token puede aparecer en otra
    capitalización según por dónde haya pasado, y una comparación exacta lo
    dejaría escapar.
    """
    resultado = texto
    for secreto in secretos:
        if not secreto or len(secreto) < 4:
            continue  # un "secreto" de 3 letras haría desaparecer texto legítimo
        bajo = resultado.lower()
        objetivo = secreto.lower()
        desde = 0
        while True:
            i = bajo.find(objetivo, desde)
            if i == -1:
                break
            resultado = resultado[:i] + "[oculto]" + resultado[i + len(secreto):]
            bajo = resultado.lower()
            desde = i + len("[oculto]")
    return resultado
