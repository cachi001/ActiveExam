"""Export a PDF del sumario de estadísticas institucionales (C-20).

PDF tabular con fpdf2 (Python puro, sin libs de sistema). Sin PII: solo agregados.
L2.5 (RN-SC-01, DD-01): el "en riesgo" PRIORIZA la revisión humana, nunca es un
veredicto ni una sanción.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

from fpdf import FPDF

from app.application.stats.charts import dashboard_png
from app.application.stats.resumen_service import FiltrosStats, ResumenStats

_AZUL = (0, 75, 168)
_GRIS = (71, 85, 105)


def _titulo(pdf: FPDF, texto: str) -> None:
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*_AZUL)
    pdf.cell(0, 8, texto, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)


def _fila(pdf: FPDF, izq: str, der: object) -> None:
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(120, 6, str(izq), border="B")
    pdf.cell(0, 6, str(der), border="B", align="R", new_x="LMARGIN", new_y="NEXT")


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
        return "sin filtros (todo el período)"
    partes: list[str] = []
    if filtros and filtros.materia_id:
        # Al filtrar por materia el sumario trae solo esa materia: usamos su nombre.
        nombre = r.por_materia[0].nombre if r.por_materia else "materia filtrada"
        partes.append(f"materia: {nombre}")
    if filtros and filtros.desde:
        partes.append(f"desde {filtros.desde[:10]}")
    if filtros and filtros.hasta:
        partes.append(f"hasta {filtros.hasta[:10]}")
    return " · ".join(partes) or "filtrado"


def resumen_a_pdf(r: ResumenStats, filtros: FiltrosStats | None = None) -> bytes:
    """Serializa el sumario a un PDF tabular (bytes)."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Encabezado
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "ActiveExam", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 13)
    pdf.cell(0, 7, "Estadísticas institucionales", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_GRIS)
    generado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.cell(0, 6, f"Generado: {generado}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Filtros: {_filtros_txt(r, filtros)}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    _titulo(pdf, "Resumen")
    _fila(pdf, "Exámenes", r.total_examenes)
    _fila(pdf, "Materias", r.total_materias)
    _fila(pdf, "Comisiones", r.total_comisiones)
    _fila(pdf, "Sesiones", r.total_sesiones)
    _fila(pdf, "Sesiones finalizadas", r.sesiones_finalizadas)
    _fila(pdf, f"En riesgo (score >= {r.umbral_riesgo})", r.sesiones_en_riesgo)
    pdf.ln(3)

    _titulo(pdf, "Distribución de scores")
    for rango, n in r.distribucion_scores.items():
        _fila(pdf, rango, n)
    pdf.ln(3)

    if r.por_materia:
        _titulo(pdf, "Sesiones por materia")
        for m in r.por_materia:
            _fila(pdf, m.nombre, f"{m.sesiones}  (en riesgo {m.en_riesgo})")
        pdf.ln(3)

    if r.top_eventos:
        _titulo(pdf, "Detectores más frecuentes")
        for e in r.top_eventos:
            _fila(pdf, e.tipo, e.cantidad)
        pdf.ln(3)

    if r.decisiones:
        _titulo(pdf, "Estado de revisión")
        for clave, n in r.decisiones.items():
            _fila(pdf, clave, n)
        pdf.ln(3)

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*_GRIS)
    pdf.multi_cell(
        0,
        5,
        'El conteo "en riesgo" prioriza la revisión humana; no es un veredicto '
        "ni una sanción. La decisión disciplinaria es siempre humana.",
    )

    # Página de GRÁFICOS (dashboard renderizado con matplotlib).
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*_AZUL)
    pdf.cell(0, 8, "Gráficos", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)
    ancho = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.image(io.BytesIO(dashboard_png(r)), w=ancho)

    return bytes(pdf.output())
