"""MODULO_LABELS: catálogo de módulos de auditoría con label (dominio puro).

Cubre el riesgo que motivó este catálogo: si se agrega un ``ModuloAuditoria``
nuevo y no se le agrega label, el filtro de Auditoría del frontend lo mostraría
con un fallback crudo en vez de romper — pero conviene detectarlo en CI. Sin
DB ni red: dominio puro (D1).
"""

from __future__ import annotations

from app.application.audit.acciones import MODULO_LABELS, ModuloAuditoria


def test_todos_los_modulos_tienen_label() -> None:
    """Cada miembro de ModuloAuditoria tiene una entrada en MODULO_LABELS."""
    faltantes = [m for m in ModuloAuditoria if m not in MODULO_LABELS]
    assert faltantes == [], f"Módulos sin label: {faltantes}"


def test_labels_no_estan_vacios() -> None:
    """Ningún label es string vacío (rompería el select del frontend en silencio)."""
    for modulo, label in MODULO_LABELS.items():
        assert label.strip() != "", f"Label vacío para {modulo}"


def test_no_hay_labels_huerfanos() -> None:
    """MODULO_LABELS no tiene entradas para módulos que ya no existen en el enum."""
    valores_enum = set(ModuloAuditoria)
    huerfanos = [m for m in MODULO_LABELS if m not in valores_enum]
    assert huerfanos == [], f"Labels huérfanos (módulo eliminado del enum): {huerfanos}"
