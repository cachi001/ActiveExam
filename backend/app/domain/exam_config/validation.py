"""Validacion PURA de los parametros del examen (C-07 D4, RN-EX-01).

Reglas de negocio que se evaluan ANTES de persistir (la presentacion solo
deserializa, D4):
- ventana temporal coherente: ``fin`` estrictamente posterior a ``inicio``.
- umbral de score dentro del rango permitido (catalog).
- detectores activos restringidos al catalogo conocido.
- politica de retencion valida.
- umbrales por detector dentro de [0,1].

Trabaja sobre tipos primitivos (str ISO-8601, float, dict) para no acoplarse a la
forma de persistencia; levanta ``InvalidExamConfigError`` con detalle por campo.
Sin framework ni infraestructura (D1) -> testeable sin DB.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.exam_config.catalog import (
    POLITICAS_RETENCION,
    UMBRAL_SCORE_MAX,
    UMBRAL_SCORE_MIN,
    es_detector_conocido,
)
from app.domain.exam_config.errors import InvalidExamConfigError


def _parse_iso(valor: str) -> datetime | None:
    """Parsea un timestamp ISO-8601; ``None`` si no es valido."""
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def validar_ventana(inicio: str, fin: str) -> dict[str, str]:
    """Valida que la ventana temporal sea coherente (fin > inicio)."""
    errores: dict[str, str] = {}
    ini = _parse_iso(inicio)
    end = _parse_iso(fin)
    if ini is None:
        errores["ventana.inicio"] = "fecha de inicio invalida (ISO-8601 esperado)"
    if end is None:
        errores["ventana.fin"] = "fecha de fin invalida (ISO-8601 esperado)"
    if ini is not None and end is not None and end <= ini:
        errores["ventana"] = "la fecha de fin debe ser posterior a la de inicio"
    return errores


def validar_umbral_score(umbral: float) -> dict[str, str]:
    """Valida que el umbral de score este en el rango permitido."""
    if not (UMBRAL_SCORE_MIN <= umbral <= UMBRAL_SCORE_MAX):
        return {
            "umbral_score": (
                f"fuera de rango [{UMBRAL_SCORE_MIN}, {UMBRAL_SCORE_MAX}]"
            )
        }
    return {}


def validar_detectores(detectores: tuple[str, ...]) -> dict[str, str]:
    """Valida que todos los detectores pertenezcan al catalogo conocido."""
    desconocidos = [d for d in detectores if not es_detector_conocido(d)]
    if desconocidos:
        return {"detectores": f"detector(es) desconocido(s): {', '.join(desconocidos)}"}
    return {}


def validar_umbrales_detector(umbrales: dict[str, float]) -> dict[str, str]:
    """Valida que los umbrales por detector esten en [0,1] y referencien
    detectores conocidos."""
    errores: dict[str, str] = {}
    for nombre, valor in umbrales.items():
        if not es_detector_conocido(nombre):
            errores[f"umbrales.{nombre}"] = "detector desconocido"
        elif not (0.0 <= float(valor) <= 1.0):
            errores[f"umbrales.{nombre}"] = "umbral fuera de [0,1]"
    return errores


def validar_retencion(politica: str) -> dict[str, str]:
    """Valida que la politica de retencion pertenezca al conjunto valido."""
    if politica not in POLITICAS_RETENCION:
        return {
            "retencion": (
                f"politica invalida; validas: {', '.join(sorted(POLITICAS_RETENCION))}"
            )
        }
    return {}


def validar_config_examen(
    *,
    inicio: str,
    fin: str,
    umbral_score: float,
    detectores: tuple[str, ...],
    umbrales_detector: dict[str, float],
    politica_retencion: str,
) -> None:
    """Valida la configuracion completa; levanta ``InvalidExamConfigError`` si hay
    cualquier parametro invalido (con TODOS los errores agregados, D4)."""
    errores: dict[str, str] = {}
    errores.update(validar_ventana(inicio, fin))
    errores.update(validar_umbral_score(umbral_score))
    errores.update(validar_detectores(detectores))
    errores.update(validar_umbrales_detector(umbrales_detector))
    errores.update(validar_retencion(politica_retencion))
    if errores:
        raise InvalidExamConfigError(errores)
