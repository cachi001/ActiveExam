"""Export a PDF del sumario de estadísticas institucionales (C-20).

Informe FORMAL con fpdf2 (Python puro): portada institucional + tablas con estilo
(banda de encabezado + filas alternadas) + página de gráficos. Sin PII: solo
agregados. L2.5 (RN-SC-01, DD-01): el "en riesgo" PRIORIZA la revisión humana,
nunca es un veredicto ni una sanción.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

from fpdf import FPDF

from app.application.stats.charts import dashboard_png
from app.application.stats.labels import etiqueta_evento
from app.application.stats.resumen_service import FiltrosStats, ResumenStats

_AZUL = (0, 75, 168)
_GRIS = (71, 85, 105)
_ZEBRA = (241, 245, 249)
DECISION_LABEL = {
    "sin_revisar": "Sin revisar",
    "pendiente": "Pendiente",
    "sin_hallazgos": "Sin hallazgos",
    "aprobado": "Aprobado",
    "caso_abierto": "Caso abierto",
}


def _filtros_txt(r: ResumenStats, filtros: FiltrosStats | None) -> str:
    activos = filtros and any(
        [
            filtros.materia_id,
            filtros.comision_id,
            filtros.examen_contenido_id,
            filtros.desde,
            filtros.hasta,
        ]
    )
    if not activos:
        return "Todo el período (sin filtros)"
    partes: list[str] = []
    if filtros and filtros.materia_id:
        nombre = r.por_materia[0].nombre if r.por_materia else "materia filtrada"
        partes.append(f"Materia: {nombre}")
    if filtros and filtros.desde:
        partes.append(f"desde {filtros.desde[:10]}")
    if filtros and filtros.hasta:
        partes.append(f"hasta {filtros.hasta[:10]}")
    return " · ".join(partes) or "Filtrado"


def _portada(pdf: FPDF, r: ResumenStats, filtros: FiltrosStats | None) -> None:
    pdf.add_page()
    # Marca institucional discreta arriba (sin redundancia).
    pdf.set_y(20)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*_AZUL)
    pdf.cell(0, 6, "ActiveExam", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_GRIS)
    pdf.cell(0, 5, "Plataforma de proctoring", new_x="LMARGIN", new_y="NEXT")

    # Título centrado verticalmente (sin subtítulo, sin íconos).
    pdf.set_y(pdf.h * 0.40)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(*_AZUL)
    pdf.cell(0, 14, "Estadísticas", align="C", new_x="LMARGIN", new_y="NEXT")
    # Regla corta centrada bajo el título.
    pdf.set_draw_color(*_AZUL)
    pdf.set_line_width(0.6)
    cx = pdf.w / 2
    y = pdf.get_y() + 2
    pdf.line(cx - 25, y, cx + 25, y)

    # Metadata al pie de la portada.
    pdf.set_y(pdf.h - 42)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_GRIS)
    generado = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    pdf.cell(0, 6, f"Generado: {generado}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Alcance: {_filtros_txt(r, filtros)}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)


def _titulo_pagina(pdf: FPDF, texto: str) -> None:
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*_AZUL)
    pdf.cell(0, 10, texto, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*_AZUL)
    pdf.set_line_width(0.5)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)


def _tabla(pdf: FPDF, titulo: str, headers: tuple[str, str], filas: list[tuple[object, object]]) -> None:
    if pdf.get_y() > pdf.h - 55:
        pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*_AZUL)
    pdf.cell(0, 8, titulo, new_x="LMARGIN", new_y="NEXT")
    # Banda de encabezado.
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(*_AZUL)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(120, 8, f"  {headers[0]}", fill=True)
    pdf.cell(0, 8, f"{headers[1]}  ", align="R", fill=True, new_x="LMARGIN", new_y="NEXT")
    # Filas alternadas.
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    for i, (izq, der) in enumerate(filas):
        fill = i % 2 == 1
        if fill:
            pdf.set_fill_color(*_ZEBRA)
        pdf.cell(120, 7, f"  {izq}", fill=fill)
        pdf.cell(0, 7, f"{der}  ", align="R", fill=fill, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)


def resumen_a_pdf(r: ResumenStats, filtros: FiltrosStats | None = None) -> bytes:
    """Serializa el sumario a un informe PDF formal (bytes)."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    _portada(pdf, r, filtros)

    # --- Página de datos ---
    pdf.add_page()
    _titulo_pagina(pdf, "Resumen")

    _tabla(
        pdf,
        "Totales del período",
        ("Métrica", "Valor"),
        [
            ("Exámenes", r.total_examenes),
            ("Materias", r.total_materias),
            ("Comisiones", r.total_comisiones),
            ("Sesiones", r.total_sesiones),
            ("Sesiones finalizadas", r.sesiones_finalizadas),
            (f"En riesgo (score {r.umbral_riesgo} o más)", r.sesiones_en_riesgo),
        ],
    )

    _tabla(
        pdf,
        "Distribución de scores",
        ("Rango de score", "Sesiones"),
        [(rango, n) for rango, n in r.distribucion_scores.items()],
    )

    if r.por_materia:
        _tabla(
            pdf,
            "Sesiones por materia",
            ("Materia", "Sesiones (en riesgo)"),
            [(m.nombre, f"{m.sesiones}  ({m.en_riesgo} en riesgo)") for m in r.por_materia],
        )

    if r.top_eventos:
        _tabla(
            pdf,
            "Eventos detectados con más frecuencia",
            ("Evento", "Veces"),
            [(etiqueta_evento(e.tipo), e.cantidad) for e in r.top_eventos],
        )

    if r.decisiones:
        _tabla(
            pdf,
            "Estado de revisión",
            ("Estado", "Sesiones"),
            [(DECISION_LABEL.get(k, k), v) for k, v in r.decisiones.items()],
        )

    # --- Página de gráficos ---
    pdf.add_page()
    _titulo_pagina(pdf, "Gráficos")
    ancho = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.image(io.BytesIO(dashboard_png(r)), w=ancho)

    return bytes(pdf.output())
