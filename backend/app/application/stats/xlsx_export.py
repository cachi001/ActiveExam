"""Export Excel (.xlsx) del sumario de estadísticas institucionales (C-20).

openpyxl con gráficos NATIVOS de Excel (BarChart / PieChart) — el archivo se abre
en Excel/LibreOffice con tablas de datos y sus gráficos interactivos. Sin PII.
L2.5: el "en riesgo" prioriza la revisión humana, nunca es un veredicto.
"""

from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.series import DataPoint
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill

from app.application.stats.charts import dashboard_png
from app.application.stats.resumen_service import FiltrosStats, ResumenStats

ORDEN_BANDAS = ["0-24", "25-49", "50-69", "70-100"]
COLOR_BANDA_HEX = {"0-24": "10B981", "25-49": "3B82F6", "50-69": "F59E0B", "70-100": "EF4444"}

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

_AZUL = "004BA8"
_HDR_FILL = PatternFill("solid", fgColor="004BA8")
_HDR_FONT = Font(bold=True, color="FFFFFF")


def _encabezado_hoja(ws, cols: list[str]) -> None:
    for i, c in enumerate(cols, start=1):
        cell = ws.cell(row=1, column=i, value=c)
        cell.fill = _HDR_FILL
        cell.font = _HDR_FONT
        cell.alignment = Alignment(horizontal="left")
    for i in range(1, len(cols) + 1):
        ws.column_dimensions[chr(64 + i)].width = 26 if i == 1 else 16


def _filtros_txt(r: ResumenStats, filtros: FiltrosStats | None) -> str:
    activos = filtros and any(
        [filtros.materia_id, filtros.comision_id, filtros.examen_contenido_id, filtros.desde, filtros.hasta]
    )
    if not activos:
        return "sin filtros (todo el período)"
    partes = []
    if filtros and filtros.materia_id:
        partes.append(f"materia: {r.por_materia[0].nombre if r.por_materia else 'filtrada'}")
    if filtros and filtros.desde:
        partes.append(f"desde {filtros.desde[:10]}")
    if filtros and filtros.hasta:
        partes.append(f"hasta {filtros.hasta[:10]}")
    return " · ".join(partes) or "filtrado"


def resumen_a_xlsx(r: ResumenStats, filtros: FiltrosStats | None = None) -> bytes:
    """Serializa el sumario a un .xlsx con tablas + gráficos nativos (bytes)."""
    wb = Workbook()

    # --- Hoja Panel: portada visual con el MISMO dashboard rico del PDF
    #     (matplotlib → PNG embebido). Garantiza que el Excel "muestre gráficos"
    #     lindos y consistentes en cualquier visor, no solo los nativos básicos.
    panel = wb.active
    panel.title = "Panel"
    panel["A1"] = "ActiveExam · Estadísticas"
    panel["A1"].font = Font(bold=True, size=14, color=_AZUL)
    panel["A2"] = f"Filtros: {_filtros_txt(r, filtros)}"
    panel["A2"].font = Font(italic=True, color="475569")
    img = XLImage(io.BytesIO(dashboard_png(r)))
    ratio = (img.height / img.width) if img.width else 0.6
    img.width = 1080
    img.height = int(1080 * ratio)
    panel.add_image(img, "A4")

    # --- Hoja Resumen ---
    ws = wb.create_sheet("Resumen")
    ws["A1"] = "ActiveExam · Estadísticas"
    ws["A1"].font = Font(bold=True, size=14, color=_AZUL)
    ws["A2"] = f"Filtros: {_filtros_txt(r, filtros)}"
    ws["A2"].font = Font(italic=True, color="475569")
    metricas = [
        ("Exámenes", r.total_examenes),
        ("Materias", r.total_materias),
        ("Comisiones", r.total_comisiones),
        ("Sesiones", r.total_sesiones),
        ("Sesiones finalizadas", r.sesiones_finalizadas),
        (f"En riesgo (score >= {r.umbral_riesgo})", r.sesiones_en_riesgo),
    ]
    fila = 4
    ws.cell(row=fila, column=1, value="Métrica").font = Font(bold=True)
    ws.cell(row=fila, column=2, value="Valor").font = Font(bold=True)
    for nombre, valor in metricas:
        fila += 1
        ws.cell(row=fila, column=1, value=nombre)
        ws.cell(row=fila, column=2, value=valor)
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 14

    # Tabla de distribución + gráfico de barras + torta.
    dist_hdr = fila + 2
    ws.cell(row=dist_hdr, column=1, value="Rango de score").font = Font(bold=True)
    ws.cell(row=dist_hdr, column=2, value="Sesiones").font = Font(bold=True)
    for i, banda in enumerate(ORDEN_BANDAS, start=1):
        ws.cell(row=dist_hdr + i, column=1, value=banda)
        ws.cell(row=dist_hdr + i, column=2, value=r.distribucion_scores.get(banda, 0))

    barras = BarChart()
    barras.title = "Distribución de scores"
    barras.type = "col"
    barras.legend = None
    datos = Reference(ws, min_col=2, min_row=dist_hdr, max_row=dist_hdr + len(ORDEN_BANDAS))
    cats = Reference(ws, min_col=1, min_row=dist_hdr + 1, max_row=dist_hdr + len(ORDEN_BANDAS))
    barras.add_data(datos, titles_from_data=True)
    barras.set_categories(cats)
    barras.height = 7
    barras.width = 12
    # Color por punto (banda) para que "lea" como la app.
    serie = barras.series[0]
    for idx, banda in enumerate(ORDEN_BANDAS):
        dp = DataPoint(idx=idx)
        dp.graphicalProperties.solidFill = COLOR_BANDA_HEX[banda]
        serie.data_points.append(dp)
    ws.add_chart(barras, "D4")

    torta = PieChart()
    torta.title = "Sesiones por nivel de score"
    torta.add_data(datos, titles_from_data=True)
    torta.set_categories(cats)
    torta.height = 7
    torta.width = 12
    ws.add_chart(torta, "D20")

    # --- Hoja Por materia ---
    _hoja_tabla_barra(
        wb,
        "Por materia",
        ["Materia", "Sesiones", "En riesgo"],
        [(m.nombre, m.sesiones, m.en_riesgo) for m in (r.por_materia or [])],
        "Sesiones por materia",
    )

    # --- Hoja Detectores ---
    _hoja_tabla_barra(
        wb,
        "Detectores",
        ["Detector", "Cantidad"],
        [(ETIQUETA_EVENTO.get(e.tipo, e.tipo.replace("_", " ")), e.cantidad) for e in (r.top_eventos or [])],
        "Detectores más frecuentes",
    )

    # --- Hoja Estado de revisión (torta) ---
    dec_items = sorted((r.decisiones or {}).items(), key=lambda kv: -kv[1])
    _hoja_tabla_barra(
        wb,
        "Estado revisión",
        ["Estado", "Sesiones"],
        [(DECISION_LABEL.get(k, k), v) for k, v in dec_items],
        "Estado de revisión",
        torta=True,
    )

    # --- Hoja Actividad por día ---
    _hoja_tabla_barra(
        wb,
        "Actividad",
        ["Fecha", "Sesiones"],
        [(d.fecha, d.sesiones) for d in (r.por_dia or [])],
        "Actividad por día",
    )

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _hoja_tabla_barra(wb, titulo_hoja, cols, filas, titulo_grafico, torta=False):
    """Crea una hoja con una tabla y su gráfico (barras por default; torta si torta=True)."""
    ws = wb.create_sheet(titulo_hoja)
    _encabezado_hoja(ws, cols)
    for i, fila in enumerate(filas, start=2):
        for j, valor in enumerate(fila, start=1):
            ws.cell(row=i, column=j, value=valor)
    n = len(filas)
    if n == 0:
        ws.cell(row=2, column=1, value="Sin datos")
        return
    # El gráfico usa la 1ra columna como categorías y la 2da como valores.
    datos = Reference(ws, min_col=2, min_row=1, max_row=1 + n)
    cats = Reference(ws, min_col=1, min_row=2, max_row=1 + n)
    chart = PieChart() if torta else BarChart()
    if not torta:
        chart.type = "bar"
        chart.legend = None
    chart.title = titulo_grafico
    chart.add_data(datos, titles_from_data=True)
    chart.set_categories(cats)
    chart.height = 8
    chart.width = 14
    ancla = chr(64 + len(cols) + 2)  # columna a la derecha de la tabla
    ws.add_chart(chart, f"{ancla}2")
