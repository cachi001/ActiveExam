"""Portada del PDF de estadísticas (C-20): antes era casi una hoja en blanco
(logo chico arriba + título flotando a mitad de página, sin contenido real).
Ahora el título centrado (fondo blanco, sin banda de color ni subtítulo —
estilo institucional fijo) lleva el resumen de KPIs debajo — se prueba que el
PDF sigue generando bytes válidos con la nueva portada.

Pura (sin DB): construye un ResumenStats mínimo a mano.
"""

from __future__ import annotations

import re

from app.application.stats.pdf_export import resumen_a_pdf
from app.application.stats.resumen_service import ElegibilidadStats, ResumenStats


def _contar_paginas(pdf_bytes: bytes) -> int:
    """Cuenta objetos `/Type /Page` (no `/Pages`, el nodo raíz del árbol) en
    el PDF crudo — no hace falta una lib de parseo de PDF para esto."""
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf_bytes))


def _resumen_minimo() -> ResumenStats:
    return ResumenStats(
        total_examenes=3,
        total_materias=2,
        total_comisiones=2,
        total_sesiones=10,
        sesiones_finalizadas=8,
        sesiones_en_riesgo=1,
        umbral_riesgo=80,
        distribucion_scores={"0-20": 5, "80-100": 1},
        elegibilidad=ElegibilidadStats(total_inscriptos=10, pueden_rendir=8, no_pueden_rendir=2),
    )


def test_resumen_a_pdf_genera_bytes_pdf_validos():
    pdf_bytes = resumen_a_pdf(_resumen_minimo())
    assert pdf_bytes[:4] == b"%PDF"


def test_resumen_a_pdf_con_listas_vacias_no_revienta():
    """por_materia/por_comision/top_eventos/decisiones vacíos: las tablas
    condicionales de la página de datos no deben ejecutarse, ni romper nada."""
    pdf_bytes = resumen_a_pdf(_resumen_minimo())
    assert len(pdf_bytes) > 1000  # un PDF de verdad, no un archivo vacío/corrupto


def test_no_hay_pagina_de_graficos_huerfana_y_casi_en_blanco():
    """BUG REAL: el dashboard (6 paneles + dona) escalado al ancho completo
    de la página es más alto que el espacio libre bajo el título "Gráficos"
    → FPDF empujaba la imagen ENTERA a la página siguiente, dejando una hoja
    con el título y nada más. Portada(1) + Resumen(1, con datos mínimos
    entran en una sola hoja) + Gráficos(1) = 3 páginas, no 4."""
    pdf_bytes = resumen_a_pdf(_resumen_minimo())
    assert _contar_paginas(pdf_bytes) == 3
