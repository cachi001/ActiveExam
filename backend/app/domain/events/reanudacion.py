"""C-72 sección 5 — Clasificación de la reanudación de una rendición (PURO).

Cuando una sesión activa se reanuda (el alumno volvió), la DURACIÓN de la ausencia
—medida server-side, nunca reportada por el cliente (regla dura #6)— decide qué
evento emitir: una recarga rápida (benigna) o una reanudación tardía (merece una
mirada del revisor). Función pura: sin DB, sin I/O.
"""

from __future__ import annotations

from app.domain.events.schema import TipoEvento

# Umbral por defecto (segundos) entre recarga rápida y reanudación tardía. Arranca
# conservador; se calibra con la distribución real de ausencias (design Open Q).
UMBRAL_REANUDACION_SEG_DEFAULT = 30


def clasificar_reanudacion(
    ausencia_seg: float, *, umbral_seg: int = UMBRAL_REANUDACION_SEG_DEFAULT
) -> TipoEvento:
    """Clasifica una reanudación por la duración de la ausencia.

    ``ausencia_seg`` por debajo del umbral → ``RECARGA_PAGINA`` (recargó y volvió
    enseguida); en el umbral o por encima → ``REANUDACION_TARDIA``."""
    if ausencia_seg < umbral_seg:
        return TipoEvento.RECARGA_PAGINA
    return TipoEvento.REANUDACION_TARDIA
