"""Parser de Moodle XML → estructuras de dominio de exam_content (C-69, C-74, C-78).

Soporta: multichoice, truefalse, cloze/multianswer, ddwtos (arrastrar y soltar
en texto), matching (emparejamiento) y shortanswer (respuesta corta) — estos
tres últimos se parsean al mismo modelo de blanks que cloze, ver más abajo.
Omite: essay, numerical, description y cualquier otro tipo desconocido.
Trackea: category → categoria_ruta por pregunta (C-74 §2.2).

Cloze (C-74 §5):
  Sintaxis de blank: {N:TIPO:OPC1~OPC2~...}
  Tipos soportados: MULTICHOICE, MULTICHOICE_S, SHORTANSWER.
  Cada opcion puede tener prefijo de correccion:
    =texto     → 100% correcto
    %N%texto   → N% de peso (N=100 → correcto)
    texto      → 0% (incorrecto, sin prefijo)
  Variantes NO soportadas en esta primera vuelta: NUMERICAL, ESSAY.

ddwtos (drag and drop into text):
  El questiontext trae placeholders [[N]] y las opciones arrastrables viven en
  <dragbox><text>...</text></dragbox> aparte, SIN un tag que diga explícitamente
  qué dragbox va en qué [[N]] — el export de Moodle no lo declara. Se infirió
  empíricamente cruzando 24 preguntas reales (campus FRM, Programación 1): los
  primeros N dragboxes, en orden de documento, son la respuesta correcta de
  [[1]]..[[N]] en ese orden; cualquier dragbox extra es un distractor compartido
  por todos los blanks. Se normaliza a `tipo="cloze"` con blanks MULTICHOICE —
  mismo modelo de datos, misma UI de rendición, misma corrección server-side que
  un cloze común; ddwtos es solo un formato de origen distinto.

matching (emparejamiento, C-78):
  Cada <subquestion> es un par estímulo/respuesta (<subquestion><text>...</text>
  <answer><text>...</text></answer></subquestion>), SIN placeholders embebidos
  en el questiontext (a diferencia de cloze/ddwtos) — la instrucción general y
  los pares viven completamente separados. Se normaliza a `tipo="cloze"` con UN
  blank tipo="matching" POR PAR: cada blank ofrece como opciones el POOL
  COMPLETO de respuestas de la pregunta (igual que Moodle, que baraja las
  respuestas entre todos los pares), con una única opción marcada correcta —
  la de SU PAR. Se resuelve por id, igual que un blank multichoice
  (`grade_calculator._BLANK_ELIGE_OPCION` incluye "matching"). texto_antes de
  cada blank lleva el estímulo (columna izquierda); menos de 2 pares válidos
  no es un emparejamiento real → se omite.

shortanswer (respuesta corta, C-78):
  Preguntas de texto libre con una lista plana de <answer fraction="N"> (igual
  forma que multichoice/truefalse, sin <subquestion>). Se normaliza a un cloze
  de UN SOLO blank tipo="shortanswer" — reusa completo el modelo de blank de
  texto libre que ya existe para cloze real (grading case-insensitive contra
  las opciones marcadas es_correcta, sin ningún cambio en esa rama). Sin
  ninguna respuesta con fraction>0 no hay nada aceptable → se omite.

_strip_html elimina <tags> pero NO toca {N:TYPE:...} ni [[N]] (usan {} y [[ ]],
no <>) — los placeholders de cloze y ddwtos sobreviven intactos al strip.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from app.application.exam_content.errors import MoodleXmlInvalidoError, MoodleXmlVacioError

_TIPOS_SOPORTADOS = frozenset(
    {"multichoice", "truefalse", "cloze", "multianswer", "ddwtos", "matching", "shortanswer"}
)

_RE_BLANK = re.compile(r"\{(\d+):(MULTICHOICE_S|MULTICHOICE|SHORTANSWER):([^}]*)\}", re.IGNORECASE)
_RE_OPT_PESO = re.compile(r"^%(\d+)%(.*)$", re.DOTALL)
_RE_DDWTOS_PLACEHOLDER = re.compile(r"\[\[(\d+)\]\]")


@dataclass
class OpcionClozeDato:
    """Opcion de un blank dentro de una pregunta cloze."""
    texto: str
    es_correcta: bool
    peso: int
    orden: int
    # Devolucion de Moodle para esta opcion (lo que va despues de `#`). Se guarda
    # aparte y NUNCA se concatena al texto: es material de repaso para despues de
    # corregir, y mezclado con la opcion le regala la respuesta al alumno (c-78).
    feedback: str = ""


@dataclass
class BlankData:
    """Hueco (blank) dentro de un texto cloze."""
    orden: int
    tipo: str
    texto_antes: str
    texto_despues: str
    opciones: list[OpcionClozeDato] = field(default_factory=list)


def _separar_feedback(texto: str) -> tuple[str, str]:
    """Parte una opcion cloze en (respuesta, feedback).

    En el formato de Moodle, `#` separa la respuesta de su devolucion:
    `=int(texto)#Convierte a entero y lanza ValueError si no puede.`

    Sin esta separacion el feedback viajaba DENTRO del texto de la opcion y el
    alumno lo veia en pantalla — y como el feedback explica por que cada opcion
    esta bien o mal, el examen se resolvia leyendo (c-78, encontrado rindiendo
    un parcial real de punta a punta).

    Se corta en el PRIMER `#`: el feedback puede tener `#` adentro y eso es
    parte del feedback, no otra separacion.
    """
    if "#" not in texto:
        return texto, ""
    respuesta, _, feedback = texto.partition("#")
    return respuesta.strip(), feedback.strip()


def _parse_opcion_cloze(raw: str) -> tuple[str, int, str]:
    """Devuelve (texto, peso, feedback) de una opcion cruda del cloze."""
    texto = raw.strip()
    if texto.startswith("="):
        limpio, feedback = _separar_feedback(texto[1:].strip())
        return html.unescape(limpio), 100, html.unescape(feedback)
    m = _RE_OPT_PESO.match(texto)
    if m:
        limpio, feedback = _separar_feedback(m.group(2).strip())
        return html.unescape(limpio), int(m.group(1)), html.unescape(feedback)
    limpio, feedback = _separar_feedback(texto)
    return html.unescape(limpio), 0, html.unescape(feedback)


def parse_cloze_blanks(texto_cloze: str) -> list[BlankData]:
    """Extrae los blanks de un texto cloze.

    Materializa los matches primero para poder acceder al anterior/siguiente
    sin re-ejecutar finditer (iterador de un solo uso).
    """
    blanks: list[BlankData] = []
    matches = list(_RE_BLANK.finditer(texto_cloze))

    for i, m in enumerate(matches):
        tipo_raw = m.group(2).upper()
        tipo = "shortanswer" if "SHORT" in tipo_raw else "multichoice"

        opciones: list[OpcionClozeDato] = []
        for j, opt_raw in enumerate(m.group(3).split("~")):
            texto_opt, peso, feedback = _parse_opcion_cloze(opt_raw)
            if texto_opt:
                opciones.append(OpcionClozeDato(
                    texto=texto_opt,
                    es_correcta=peso >= 100,
                    peso=peso,
                    orden=j,
                    feedback=feedback,
                ))

        inicio_anterior = matches[i - 1].end() if i > 0 else 0
        fin_siguiente = matches[i + 1].start() if i + 1 < len(matches) else len(texto_cloze)

        blanks.append(BlankData(
            orden=i,
            tipo=tipo,
            texto_antes=texto_cloze[inicio_anterior:m.start()],
            texto_despues=texto_cloze[m.end():fin_siguiente],
            opciones=opciones,
        ))

    return blanks


_TRUE_FALSE_MAP = {"true": "Verdadero", "false": "Falso"}



# Tags de bloque: al borrarlos hay que dejar un salto de línea en su lugar, o
# el texto de dos bloques distintos queda pegado ("...nombre: ")" + "{blank}"
# sin espacio de por medio si el HTML fuente no trae un salto literal — bug
# real visto en producción con el export de Moodle de campustest, cuando
# `<br>` separaba dos blanks dentro del mismo `<p>` sin whitespace alrededor).
_RE_BLOQUE_A_SALTO = re.compile(
    r"</?(?:p|div|li|ul|ol|table|thead|tbody|tr|h[1-6])\b[^>]*>|<br\s*/?>",
    re.IGNORECASE,
)
# Celdas de tabla: separador más liviano (espacio), no salto de línea, para
# que una fila de tabla siga leyéndose como una fila.
_RE_CELDA_A_ESPACIO = re.compile(r"<t[dh]\b[^>]*>", re.IGNORECASE)

# Marcadores invisibles (Unicode Private Use Area, nunca aparecen en texto
# real) que delimitan tramos que el autor marcó como código con <code> en
# Moodle. Sobreviven al strip de tags porque se sustituyen ANTES del strip
# genérico; el frontend los usa para decidir qué renderizar en monoespaciado,
# igual que el resaltado que aplica Moodle nativamente a esos mismos <code>.
CODE_MARCA_INICIO = ""
CODE_MARCA_FIN = ""
_RE_CODE_INICIO = re.compile(r"<code\b[^>]*>", re.IGNORECASE)
_RE_CODE_FIN = re.compile(r"</code>", re.IGNORECASE)


def _strip_html(text: str) -> str:
    text = _RE_BLOQUE_A_SALTO.sub("\n", text)
    text = _RE_CELDA_A_ESPACIO.sub(" ", text)
    text = _RE_CODE_INICIO.sub(CODE_MARCA_INICIO, text)
    text = _RE_CODE_FIN.sub(CODE_MARCA_FIN, text)
    text = re.sub(r"<[^>]+>", "", text)
    # Decodificar entidades (&lt;, &amp;, &nbsp;...) DESPUÉS de quitar los tags
    # reales — si se decodificara antes, un "&lt;=" podría convertirse en "<="
    # y ser confundido por el regex de tags con la apertura de uno.
    text = html.unescape(text)
    # &nbsp; (\xa0) es el "línea vacía" que usa Moodle entre bloques — tratarlo
    # como espacio normal para que colapse igual que una línea en blanco real.
    text = text.replace("\xa0", " ")
    # Colapsar espacios/tabs repetidos (sin tocar los saltos de línea que
    # acabamos de insertar) y líneas en blanco de más.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@dataclass
class OpcionData:
    texto: str
    es_correcta: bool
    orden: int = 0


@dataclass
class PreguntaData:
    enunciado: str
    tipo: str
    opciones: list[OpcionData] = field(default_factory=list)
    orden: int = 0
    categoria_ruta: list[str] | None = None
    blanks: list[BlankData] = field(default_factory=list)


@dataclass
class PreguntaOmitida:
    tipo: str
    nombre: str


@dataclass
class ParseResult:
    preguntas: list[PreguntaData]
    omitidas: list[PreguntaOmitida]


def parse_moodle_xml(xml_bytes: bytes) -> ParseResult:
    """Parsea un export Moodle XML y devuelve preguntas + omitidas.

    Raises:
        MoodleXmlInvalidoError: si el XML es malformado.
        MoodleXmlVacioError: si no hay preguntas de tipo soportado.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise MoodleXmlInvalidoError(f"XML malformado: {exc}") from exc

    preguntas: list[PreguntaData] = []
    omitidas: list[PreguntaOmitida] = []
    categoria_activa: list[str] | None = None

    for i, question in enumerate(root.findall("question")):
        tipo = question.get("type", "")

        if tipo == "category":
            cat_el = question.find("category/text")
            if cat_el is not None and cat_el.text:
                ruta = cat_el.text.strip()
                for prefix in ("$course$/top/", "$course$/"):
                    if ruta.startswith(prefix):
                        ruta = ruta[len(prefix):]
                        break
                segmentos = [s.strip() for s in ruta.split("/") if s.strip()]
                categoria_activa = segmentos if segmentos else None
            continue

        nombre_el = question.find("name/text")
        nombre = nombre_el.text if nombre_el is not None and nombre_el.text else f"pregunta_{i}"

        if tipo not in _TIPOS_SOPORTADOS:
            omitidas.append(PreguntaOmitida(tipo=tipo, nombre=nombre))
            continue

        if tipo in ("cloze", "multianswer"):
            preguntas.append(_parse_cloze(question, categoria_activa, len(preguntas)))
        elif tipo == "ddwtos":
            parsed = _parse_ddwtos(question, categoria_activa, len(preguntas))
            if parsed is None:
                omitidas.append(
                    PreguntaOmitida(tipo=tipo, nombre=f"{nombre} (sin mapeo de opciones)")
                )
            else:
                preguntas.append(parsed)
        elif tipo == "matching":
            parsed = _parse_matching(question, categoria_activa, len(preguntas))
            if parsed is None:
                omitidas.append(
                    PreguntaOmitida(tipo=tipo, nombre=f"{nombre} (menos de 2 pares válidos)")
                )
            else:
                preguntas.append(parsed)
        elif tipo == "shortanswer":
            parsed = _parse_shortanswer(question, categoria_activa, len(preguntas))
            if parsed is None:
                omitidas.append(
                    PreguntaOmitida(tipo=tipo, nombre=f"{nombre} (sin respuesta correcta)")
                )
            else:
                preguntas.append(parsed)
        else:
            enunciado = _parse_enunciado(question)
            opciones = _parse_opciones(question, tipo)
            preguntas.append(
                PreguntaData(
                    enunciado=enunciado,
                    tipo=tipo,
                    opciones=opciones,
                    orden=len(preguntas),
                    categoria_ruta=list(categoria_activa) if categoria_activa else None,
                )
            )

    if not preguntas:
        raise MoodleXmlVacioError("El XML no contiene preguntas de tipo soportado.")

    return ParseResult(preguntas=preguntas, omitidas=omitidas)


def _parse_cloze(
    question: ET.Element,
    categoria_activa: list[str] | None,
    orden: int,
) -> PreguntaData:
    text_el = question.find("questiontext/text")
    raw_text = text_el.text if text_el is not None and text_el.text else ""
    enunciado = _strip_html(raw_text)
    blanks = parse_cloze_blanks(enunciado)
    return PreguntaData(
        enunciado=enunciado,
        tipo="cloze",
        opciones=[],
        orden=orden,
        categoria_ruta=list(categoria_activa) if categoria_activa else None,
        blanks=blanks,
    )


def _parse_ddwtos(
    question: ET.Element,
    categoria_activa: list[str] | None,
    orden: int,
) -> PreguntaData | None:
    """Parsea una pregunta ddwtos a blanks MULTICHOICE (ver docstring del módulo).

    None si no hay placeholders [[N]] en el texto, o si hay menos dragboxes que
    placeholders (no alcanza para mapear una respuesta correcta a cada blank) —
    en ambos casos el caller la reporta como omitida en vez de importar algo
    potencialmente incorrecto.
    """
    text_el = question.find("questiontext/text")
    raw_text = text_el.text if text_el is not None and text_el.text else ""
    enunciado = _strip_html(raw_text)

    matches = list(_RE_DDWTOS_PLACEHOLDER.finditer(enunciado))
    if not matches:
        return None

    dragboxes: list[str] = []
    for db in question.findall("dragbox"):
        db_text_el = db.find("text")
        texto = db_text_el.text if db_text_el is not None and db_text_el.text else ""
        dragboxes.append(html.unescape(texto.strip()))

    n = len(matches)
    if len(dragboxes) < n:
        return None

    # Los primeros N dragboxes (orden de documento) son la respuesta correcta de
    # [[1]]..[[N]] en ese orden; el resto son distractores del pool compartido.
    correctas = dragboxes[:n]

    blanks: list[BlankData] = []
    for i, m in enumerate(matches):
        inicio_anterior = matches[i - 1].end() if i > 0 else 0
        fin_siguiente = matches[i + 1].start() if i + 1 < len(matches) else len(enunciado)
        correcta_texto = correctas[i]
        opciones = [
            OpcionClozeDato(
                texto=texto,
                es_correcta=(texto == correcta_texto),
                peso=100 if texto == correcta_texto else 0,
                orden=j,
            )
            for j, texto in enumerate(dragboxes)
        ]
        blanks.append(
            BlankData(
                orden=i,
                tipo="multichoice",
                texto_antes=enunciado[inicio_anterior:m.start()],
                texto_despues=enunciado[m.end():fin_siguiente],
                opciones=opciones,
            )
        )

    return PreguntaData(
        enunciado=enunciado,
        tipo="cloze",
        opciones=[],
        orden=orden,
        categoria_ruta=list(categoria_activa) if categoria_activa else None,
        blanks=blanks,
    )


def _parse_matching(
    question: ET.Element,
    categoria_activa: list[str] | None,
    orden: int,
) -> PreguntaData | None:
    """Parsea una pregunta matching a blanks tipo "matching" (ver docstring
    del módulo). None si hay menos de 2 pares estímulo/respuesta válidos —
    con uno solo no hay nada que emparejar.
    """
    instruccion_el = question.find("questiontext/text")
    instruccion_raw = instruccion_el.text if instruccion_el is not None and instruccion_el.text else ""
    instruccion = _strip_html(instruccion_raw)

    pares: list[tuple[str, str]] = []
    for sub in question.findall("subquestion"):
        estimulo_el = sub.find("text")
        estimulo_raw = estimulo_el.text if estimulo_el is not None and estimulo_el.text else ""
        estimulo = _strip_html(estimulo_raw)
        respuesta_el = sub.find("answer/text")
        respuesta_raw = respuesta_el.text if respuesta_el is not None and respuesta_el.text else ""
        respuesta = html.unescape(respuesta_raw.strip())
        if estimulo and respuesta:
            pares.append((estimulo, respuesta))

    if len(pares) < 2:
        return None

    pool_respuestas = [r for _, r in pares]
    blanks: list[BlankData] = []
    for i, (estimulo, respuesta_correcta) in enumerate(pares):
        opciones = [
            OpcionClozeDato(
                texto=texto,
                es_correcta=(texto == respuesta_correcta),
                peso=100 if texto == respuesta_correcta else 0,
                orden=j,
            )
            for j, texto in enumerate(pool_respuestas)
        ]
        prefijo = f"{instruccion}\n\n" if i == 0 else "\n"
        blanks.append(
            BlankData(
                orden=i,
                tipo="matching",
                texto_antes=f"{prefijo}{estimulo}:  ",
                texto_despues="",
                opciones=opciones,
            )
        )

    return PreguntaData(
        enunciado=instruccion,
        tipo="cloze",
        opciones=[],
        orden=orden,
        categoria_ruta=list(categoria_activa) if categoria_activa else None,
        blanks=blanks,
    )


def _parse_shortanswer(
    question: ET.Element,
    categoria_activa: list[str] | None,
    orden: int,
) -> PreguntaData | None:
    """Parsea una pregunta shortanswer a un cloze de UN blank tipo
    "shortanswer" (ver docstring del módulo). None si ninguna respuesta tiene
    fraction > 0 — sin eso no hay nada aceptable que comparar.
    """
    text_el = question.find("questiontext/text")
    raw_text = text_el.text if text_el is not None and text_el.text else ""
    enunciado = _strip_html(raw_text)

    opciones: list[OpcionClozeDato] = []
    for j, answer in enumerate(question.findall("answer")):
        fraction_str = answer.get("fraction", "0")
        try:
            fraction = float(fraction_str)
        except ValueError:
            fraction = 0.0
        texto_el = answer.find("text")
        raw = texto_el.text if texto_el is not None and texto_el.text else ""
        texto = html.unescape(raw.strip())
        if texto:
            opciones.append(
                OpcionClozeDato(texto=texto, es_correcta=fraction > 0, peso=int(fraction), orden=j)
            )

    if not any(o.es_correcta for o in opciones):
        return None

    blank = BlankData(
        orden=0,
        tipo="shortanswer",
        texto_antes=f"{enunciado}\n\n" if enunciado else "",
        texto_despues="",
        opciones=opciones,
    )
    return PreguntaData(
        enunciado=enunciado,
        tipo="cloze",
        opciones=[],
        orden=orden,
        categoria_ruta=list(categoria_activa) if categoria_activa else None,
        blanks=[blank],
    )


def _parse_enunciado(question: ET.Element) -> str:
    text_el = question.find("questiontext/text")
    if text_el is None or not text_el.text:
        return ""
    return _strip_html(text_el.text)


def _parse_opciones(question: ET.Element, tipo: str) -> list[OpcionData]:
    opciones: list[OpcionData] = []
    for j, answer in enumerate(question.findall("answer")):
        fraction_str = answer.get("fraction", "0")
        try:
            fraction = float(fraction_str)
        except ValueError:
            fraction = 0.0

        text_el = answer.find("text")
        raw_text = text_el.text if text_el is not None and text_el.text else ""
        texto = _strip_html(raw_text)

        if tipo == "truefalse":
            texto = _TRUE_FALSE_MAP.get(texto.lower(), texto)

        opciones.append(
            OpcionData(
                texto=texto,
                es_correcta=fraction > 0,
                orden=j,
            )
        )
    return opciones
