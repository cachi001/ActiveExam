"""Export de listados académicos a Excel y PDF (c-78 §13, E-10).

Existe porque hay campus SIN API: la nota se termina cargando a mano, y para eso
hace falta el listado en un archivo, no en una pantalla paginada. Lo mismo para
cruzar los inscriptos de una comisión contra el padrón del campus.

Dos exportables, un solo motor:
  - inscriptos de una comisión (apellido, nombre, usuario, email, inscripción)
  - notas de un examen (alumno, nota, estado de entrega, estado en el campus)

El motor (`tabla_a_xlsx` / `tabla_a_pdf`) es genérico a propósito: los dos
exportables difieren solo en columnas y encabezado, y duplicar el armado del
Workbook/FPDF garantiza que uno de los dos se quede atrás. Mismo criterio de
estilo que `audit/export.py`, del que se toma el patrón ya validado (incluida la
transliteración a latin-1 que FPDF necesita).

PRIVACIDAD (Ley 25.326): estos archivos llevan datos personales de alumnos. Se
exporta lo MÍNIMO para el propósito declarado — identificar a la persona en el
campus. No van scores de proctoring, ni eventos, ni evidencia.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

_AZUL = "004BA8"
_HDR_FILL = PatternFill("solid", fgColor=_AZUL)
_HDR_FONT = Font(bold=True, color="FFFFFF")

# Ver el comentario extenso en audit/export.py: FPDF con fuente core solo soporta
# latin-1, y las rayas/comillas tipográficas quedaban como "?".
_REEMPLAZOS_PDF_LATIN1 = {
    "—": "-",
    "–": "-",
    "…": "...",
    "→": "->",
    "«": '"',
    "»": '"',
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "·": "-",
}


def _txt(valor: str) -> str:
    """Translitera lo tipográfico y reemplaza lo que aun así no entra en latin-1."""
    texto = valor or ""
    for feo, equivalente in _REEMPLAZOS_PDF_LATIN1.items():
        texto = texto.replace(feo, equivalente)
    return texto.encode("latin-1", "replace").decode("latin-1")


def fecha_legible(valor) -> str:
    """datetime/ISO → 'dd/mm/aaaa hh:mm'. Vacío si no hay dato (nunca 'None')."""
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).strftime(
            "%d/%m/%Y %H:%M"
        )
    except (ValueError, TypeError):
        return str(valor)


@dataclass(frozen=True, slots=True)
class Columna:
    """Una columna del export: su título y su ancho en cada formato."""

    titulo: str
    #: Ancho en "caracteres" de openpyxl.
    ancho_xlsx: int
    #: Ancho en mm para FPDF.
    ancho_pdf: int


def tabla_a_xlsx(
    *,
    titulo: str,
    subtitulo: str,
    columnas: list[Columna],
    filas: list[list[str]],
    nombre_hoja: str = "Listado",
) -> bytes:
    """Tabla genérica como .xlsx, con cabecera de contexto. Devuelve los bytes.

    La cabecera (título, subtítulo, fecha de generación y cantidad de filas) no
    es decoración: un listado suelto sin decir de qué comisión y de cuándo es no
    se puede usar para cruzar nada.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = nombre_hoja[:31] or "Listado"

    ws["A1"] = titulo
    ws["A1"].font = Font(bold=True, size=14, color=_AZUL)
    ws["A2"] = subtitulo
    ws["A3"] = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A4"] = f"Filas: {len(filas)}"

    fila_encabezado = 6
    for i, col in enumerate(columnas, start=1):
        celda = ws.cell(row=fila_encabezado, column=i, value=col.titulo)
        celda.fill = _HDR_FILL
        celda.font = _HDR_FONT
        celda.alignment = Alignment(horizontal="left")
        ws.column_dimensions[chr(64 + i)].width = col.ancho_xlsx

    for j, fila in enumerate(filas, start=fila_encabezado + 1):
        for i, valor in enumerate(fila, start=1):
            ws.cell(row=j, column=i, value=valor)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


#: Margen lateral que aplica FPDF por defecto (10 mm de cada lado).
_MARGEN_LATERAL_MM = 10
#: Ancho de página A4 en mm, en cada orientación.
_A4_ANCHO_MM = {False: 210, True: 297}


def ancho_util_mm(apaisado: bool) -> int:
    """Milímetros disponibles para la tabla, descontando los márgenes.

    Las celdas se dibujan una al lado de la otra con ancho fijo: lo que se pasa
    de este número queda FUERA del papel, sin error y sin aviso. Por eso el ancho
    de las columnas se valida contra este valor (`test_export_pdf_columnas_entran`).
    """
    return _A4_ANCHO_MM[bool(apaisado)] - 2 * _MARGEN_LATERAL_MM


def tabla_a_pdf(
    *,
    titulo: str,
    subtitulo: str,
    columnas: list[Columna],
    filas: list[list[str]],
    apaisado: bool = False,
) -> bytes:
    """Tabla genérica como PDF. Devuelve los bytes.

    El PDF es una TABLA para imprimir/mirar: los textos largos se recortan al
    ancho de su columna. El archivo completo sin recortes es el Excel (mismo
    criterio que el export de auditoría).
    """
    pdf = FPDF(orientation="L" if apaisado else "P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(0, 75, 168)
    pdf.cell(0, 9, _txt(titulo), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 5, _txt(subtitulo), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        5,
        _txt(
            f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} - "
            f"Filas: {len(filas)}"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(3)

    anchos = [c.ancho_pdf for c in columnas]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(0, 75, 168)
    pdf.set_text_color(255, 255, 255)
    for ancho, col in zip(anchos, columnas):
        pdf.cell(ancho, 8, _txt(col.titulo), border=0, fill=True, align="L")
    pdf.ln(8)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(30, 30, 30)
    for i, fila in enumerate(filas):
        pdf.set_fill_color(245, 247, 250) if i % 2 == 0 else pdf.set_fill_color(
            255, 255, 255
        )
        for ancho, valor in zip(anchos, fila):
            maximo = max(4, int(ancho / 1.7))
            texto = valor if len(valor) <= maximo else valor[: maximo - 3] + "..."
            pdf.cell(ancho, 6, _txt(texto), border=0, fill=True, align="L")
        pdf.ln(6)

    salida = pdf.output()
    return bytes(salida) if not isinstance(salida, bytes) else salida


# ---------------------------------------------------------------------------
# Inscriptos de una comisión (E-10)
# ---------------------------------------------------------------------------

# Las columnas para cruzar contra el padrón de Moodle, MÁS la elegibilidad de cada
# alumno. Sin consentimiento o sin biometría el alumno no puede rendir, y ese es el
# motivo por el que se descarga este listado antes del examen: saber a quién hay que
# avisarle. La pantalla ya lo mostraba por alumno; el archivo lo omitía, así que
# había que revisar uno por uno en la web lo que el export debía resolver de una.
#: El PDF de inscriptos va APAISADO. Con las 8 columnas, en A4 vertical entran
#: 186 mm y la tabla necesita más: las tres de elegibilidad quedaban fuera del
#: papel, así que en el teléfono el archivo se cortaba en "Inscripción" y no se
#: veía justamente el dato por el que se abre el listado.
INSCRIPTOS_APAISADO = True

COLUMNAS_INSCRIPTOS = [
    Columna("Apellido", 26, 26),
    Columna("Nombre", 26, 26),
    Columna("Usuario", 26, 24),
    # 50 mm entra un mail institucional completo (juan.perez@frm.utn.edu.ar).
    # Uno más largo se recorta: el archivo sin recortes es el Excel.
    Columna("Email", 38, 50),
    # 30 mm y no menos: con 26 la fecha salía como "27/08/2026 1...".
    Columna("Inscripción", 20, 30),
    Columna("Consentimiento", 16, 24),
    Columna("Biometría", 14, 20),
    # Va última y con el motivo adentro: es la columna que se lee primero cuando
    # se abre el archivo para ver quién se queda afuera. Se le deja todo el ancho
    # que sobra porque su texto es el más largo ("NO — Falta consentimiento y
    # biometría") y recortarlo deja el motivo a medias, que es peor que no tenerlo.
    Columna("¿Puede rendir?", 34, 72),
]


def _si_no(valor: object) -> str:
    """Sí/No legible. Un campo ausente se informa como No, nunca como Sí: decir
    que sí sin dato haría creer que el alumno está listo cuando no se sabe."""
    return "Sí" if valor is True else "No"


def _puede_rendir_legible(inscripto) -> str:
    """"Sí" o "NO — {motivo}". Sin motivo, "NO" a secas: la ausencia de razón no
    puede volverse un "sí" por descarte."""
    if getattr(inscripto, "puede_rendir", False) is True:
        return "Sí"
    razon = (getattr(inscripto, "razon", None) or "").strip()
    return f"NO — {razon}" if razon else "NO"


def filas_inscriptos(inscriptos: list) -> list[list[str]]:
    """Proyecta los inscriptos a filas de export (función PURA)."""
    return [
        [
            getattr(i, "apellido", "") or "",
            getattr(i, "nombre", "") or "",
            getattr(i, "username", "") or "",
            getattr(i, "email", "") or "",
            fecha_legible(getattr(i, "inscripto_en", None)),
            _si_no(getattr(i, "consentimiento_vigente", None)),
            _si_no(getattr(i, "biometria_vigente", None)),
            _puede_rendir_legible(i),
        ]
        for i in inscriptos
    ]


# ---------------------------------------------------------------------------
# Notas de un examen (E-10)
# ---------------------------------------------------------------------------

#: También apaisado: seis columnas con emails y etiquetas largas no entran en
#: vertical. La orientación vive acá, al lado de los anchos que la determinan,
#: para que agregar una columna y validar que entre sea una sola decisión.
NOTAS_APAISADO = True

COLUMNAS_NOTAS = [
    Columna("Alumno", 30, 45),
    Columna("Usuario", 24, 36),
    Columna("Email", 34, 50),
    Columna("Nota", 10, 18),
    Columna("Entrega", 18, 26),
    Columna("Estado en el campus", 26, 38),
]

# Etiquetas legibles del estado de write-back. El archivo lo lee una persona que
# está cargando notas a mano: 'sin_token' no le dice nada.
_ETIQUETA_ESTADO_CAMPUS = {
    "pendiente": "Pendiente de cargar",
    "enviado": "Cargada (confirmada por el campus)",
    "fallido": "Falló el envío",
    "sin_token": "Sin conexión al campus",
    "manual": "Cargada a mano",
}

_ETIQUETA_ENTREGA = {
    "no_finalizada": "No entregó",
    "en_revision": "En revisión",
    "revisada": "Revisada",
    "finalizada": "Entregada",
}


def filas_notas(resultados: list) -> list[list[str]]:
    """Proyecta los resultados de un examen a filas de export (función PURA)."""
    filas: list[list[str]] = []
    for r in resultados:
        nota = getattr(r, "nota", None)
        estado = getattr(r, "estado_moodle", "") or ""
        entrega = getattr(r, "estado_entrega", "") or ""
        filas.append(
            [
                getattr(r, "alumno_nombre", None) or getattr(r, "alumno_idnumber", "") or "",
                getattr(r, "alumno_idnumber", "") or "",
                getattr(r, "alumno_email", "") or "",
                "" if nota is None else f"{float(nota):.2f}",
                _ETIQUETA_ENTREGA.get(entrega, entrega),
                _ETIQUETA_ESTADO_CAMPUS.get(estado, estado),
            ]
        )
    return filas
