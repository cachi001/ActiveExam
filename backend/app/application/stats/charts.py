"""Render de gráficos de estadísticas (C-20) como PNG para el export PDF.

Usa matplotlib en backend headless ('Agg'). La paleta ESPEJA la del frontend
(COLOR_BANDA) para que el PDF "lea" igual que la pantalla. L2.5: los gráficos
informan/priorizan; no emiten veredicto.
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # backend sin display (container)
import matplotlib.pyplot as plt  # noqa: E402

from app.application.stats.resumen_service import ResumenStats  # noqa: E402

# Paleta por banda de score (igual que el frontend).
COLOR_BANDA = {"0-24": "#10b981", "25-49": "#3b82f6", "50-69": "#f59e0b", "70-100": "#ef4444"}
ORDEN_BANDAS = ["0-24", "25-49", "50-69", "70-100"]
_TEAL = "#0d9488"
_INDIGO = "#6366f1"
_AZUL = "#3b82f6"
_ROJO = "#ef4444"

ETIQUETA_EVENTO = {
    "rostro_ausente": "Rostro ausente",
    "multiples_rostros": "Múltiples rostros",
    "mirada_desviada_sostenida": "Mirada desviada",
    "perdida_de_foco": "Pérdida de foco",
    "cambio_pestana": "Cambio de pestaña",
    "salida_pantalla_completa": "Salió pantalla completa",
    "copiar_pegar": "Copiar / pegar",
    "monitor_adicional": "Monitor adicional",
    "corte_conectividad_prolongado": "Corte de conexión",
    "reanudacion_tardia": "Reanudación tardía",
    "recarga_pagina": "Recarga de página",
}
DECISION_LABEL = {
    "sin_revisar": "Sin revisar",
    "pendiente": "Pendiente",
    "sin_hallazgos": "Sin hallazgos",
    "aprobado": "Aprobado",
    "caso_abierto": "Caso abierto",
}
DECISION_COLOR = {
    "sin_revisar": "#94a3b8",
    "pendiente": "#3b82f6",
    "sin_hallazgos": "#10b981",
    "aprobado": "#10b981",
    "caso_abierto": "#ef4444",
}


def _sin_datos(ax, titulo: str) -> None:
    ax.set_title(titulo, fontsize=11, fontweight="bold", loc="left")
    ax.text(0.5, 0.5, "Sin datos", ha="center", va="center", color="#94a3b8", fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def _ax_composicion(ax, r: ResumenStats) -> None:
    valores = [r.distribucion_scores.get(b, 0) for b in ORDEN_BANDAS]
    if sum(valores) == 0:
        _sin_datos(ax, "Sesiones por nivel de score")
        return
    colores = [COLOR_BANDA[b] for b in ORDEN_BANDAS]
    datos = [(b, v, c) for b, v, c in zip(ORDEN_BANDAS, valores, colores) if v > 0]
    ax.pie(
        [d[1] for d in datos],
        labels=[d[0] for d in datos],
        colors=[d[2] for d in datos],
        autopct="%1.0f%%",
        startangle=90,
        wedgeprops={"width": 0.42, "edgecolor": "white"},
        textprops={"fontsize": 8},
    )
    ax.set_title("Sesiones por nivel de score", fontsize=11, fontweight="bold", loc="left")


def _ax_distribucion(ax, r: ResumenStats) -> None:
    valores = [r.distribucion_scores.get(b, 0) for b in ORDEN_BANDAS]
    ax.bar(ORDEN_BANDAS, valores, color=[COLOR_BANDA[b] for b in ORDEN_BANDAS])
    ax.set_title("Distribución de scores", fontsize=11, fontweight="bold", loc="left")
    for i, v in enumerate(valores):
        if v:
            ax.text(i, v, str(v), ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_ylim(0, max(valores + [1]) * 1.2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)


def _ax_por_materia(ax, r: ResumenStats) -> None:
    items = list(r.por_materia or [])[:8]
    if not items:
        _sin_datos(ax, "Sesiones por materia")
        return
    items.reverse()  # el más poblado arriba
    nombres = [m.nombre[:22] for m in items]
    seguras = [m.sesiones - m.en_riesgo for m in items]
    riesgo = [m.en_riesgo for m in items]
    ax.barh(nombres, seguras, color=_AZUL, label="Otras")
    ax.barh(nombres, riesgo, left=seguras, color=_ROJO, label="En riesgo")
    ax.set_title("Sesiones por materia", fontsize=11, fontweight="bold", loc="left")
    ax.legend(fontsize=7, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)


def _ax_top_eventos(ax, r: ResumenStats) -> None:
    items = list(r.top_eventos or [])[:8]
    if not items:
        _sin_datos(ax, "Detectores más frecuentes")
        return
    items = list(reversed(items))
    nombres = [ETIQUETA_EVENTO.get(e.tipo, e.tipo.replace("_", " ")) for e in items]
    ax.barh(nombres, [e.cantidad for e in items], color=_TEAL)
    ax.set_title("Detectores más frecuentes", fontsize=11, fontweight="bold", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)


def _ax_decisiones(ax, r: ResumenStats) -> None:
    conteos = r.decisiones or {}
    items = sorted(conteos.items(), key=lambda kv: -kv[1])
    if not items or sum(v for _, v in items) == 0:
        _sin_datos(ax, "Estado de revisión")
        return
    ax.pie(
        [v for _, v in items],
        labels=[DECISION_LABEL.get(k, k) for k, _ in items],
        colors=[DECISION_COLOR.get(k, "#8b5cf6") for k, _ in items],
        autopct="%1.0f%%",
        startangle=90,
        wedgeprops={"width": 0.42, "edgecolor": "white"},
        textprops={"fontsize": 8},
    )
    ax.set_title("Estado de revisión", fontsize=11, fontweight="bold", loc="left")


def _ax_por_dia(ax, r: ResumenStats) -> None:
    items = list(r.por_dia or [])
    if not items:
        _sin_datos(ax, "Actividad por día")
        return
    fechas = [d.fecha[5:] for d in items]
    valores = [d.sesiones for d in items]
    ax.bar(fechas, valores, color=_INDIGO)
    ax.set_title("Actividad por día", fontsize=11, fontweight="bold", loc="left")
    ax.set_ylim(0, max(valores + [1]) * 1.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=7)
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(45)
        lbl.set_ha("right")


def dashboard_png(r: ResumenStats) -> bytes:
    """Un PNG con los 6 gráficos (grid 3x2) para embeber en el PDF."""
    fig, axes = plt.subplots(3, 2, figsize=(9.6, 11.0))
    _ax_composicion(axes[0][0], r)
    _ax_distribucion(axes[0][1], r)
    _ax_top_eventos(axes[1][0], r)
    _ax_decisiones(axes[1][1], r)
    _ax_por_materia(axes[2][0], r)
    _ax_por_dia(axes[2][1], r)
    fig.tight_layout(pad=2.0)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
