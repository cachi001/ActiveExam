"""Export de auditoría a PDF: FPDF core (Helvetica) solo soporta latin-1.

BUG REAL encontrado en producción: rayas tipográficas ("—", "–"), puntos
suspensivos ("…") y flechas ("→") usados en labels.py y en los propósitos
armados por el router (ej. "Registro de auditoría — Active Exam") NO están en
latin-1 — `_txt()` los reemplazaba por "?" en vez de transliterarlos, así que
el PDF (nunca el Excel, que es UTF-8 nativo) mostraba "Registro de auditoría ?
Active Exam", "canjeando su contraseña ?", etc.

Pura (sin DB).
"""

from __future__ import annotations

from app.application.audit.export import _txt, auditoria_a_pdf


def test_raya_se_translitera_a_guion_no_a_signo_de_pregunta():
    assert _txt("Registro de auditoría — Active Exam") == "Registro de auditoría - Active Exam"


def test_puntos_suspensivos_se_transliteran():
    assert _txt("texto muy largo…") == "texto muy largo..."


def test_flecha_se_translitera():
    assert _txt("antes → después") == "antes -> después"


def test_caracter_realmente_no_soportado_sigue_cayendo_a_signo_de_pregunta():
    # Un emoji no tiene equivalente latin-1 razonable: fallback explícito,
    # no debe reventar la generación del PDF.
    assert _txt("nota 🎉") == "nota ?"


def test_acentos_normales_pasan_intactos():
    # Esto NUNCA estuvo roto — confirma que el fix no rompe el caso normal.
    assert _txt("comisión, año, informática, ñandú") == "comisión, año, informática, ñandú"


def test_auditoria_a_pdf_no_revienta_con_entradas_con_raya():
    class _Entrada:
        id = "1"
        actor = "admin@x"
        actor_nombre = "Admin Sistema"
        actor_email = "admin@x"
        timestamp = "2026-08-01 00:00:00+00:00"
        accion = "moodle_credencial.conectar"
        modulo = "MOODLE"
        proposito = "Conectó su cuenta del campus — con guion largo de prueba"

    pdf_bytes = auditoria_a_pdf([_Entrada()])
    assert pdf_bytes[:4] == b"%PDF"
