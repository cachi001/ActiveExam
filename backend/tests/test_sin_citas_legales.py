"""Ningún texto que lea una persona cita normativa.

Decisión del dueño (29/8/2026): las citas legales se sacan de todo lo que ve un
alumno o un administrador. A un alumno lo confunden y no lo ayudan a entender qué
se hace con sus datos.

Alcance deliberado: **texto visible**, no comentarios de código. Un comentario que
menciona la norma no lo lee nadie más que quien programa, y borrarlo de ahí solo
agrega ruido al historial.

Ya había dos tests defendiendo esto (`glossary.test.ts` y
`test_consentimiento_dice_lo_que_hacemos.py`), pero cubrían el glosario y el texto
del consentimiento y nada más. Se coló por tres lugares que ninguno miraba: el pie
del panel del glosario, un mensaje de validación y una fila vieja en la base.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]

_PATRONES = (re.compile(r"25\.326"), re.compile(r"\b25326\b"))

#: Los tests que verifican la ausencia tienen que nombrar lo que buscan.
_EXCEPCIONES = {
    "frontend/src/config/glossary.test.ts",
}

#: Comentarios de una línea y bloques, en TS/TSX y en Python.
_COMENTARIO_LINEA = re.compile(r"(^|\s)//.*$", re.MULTILINE)
_COMENTARIO_BLOQUE = re.compile(r"/\*.*?\*/", re.DOTALL)
_JSX_COMENTARIO = re.compile(r"\{\s*/\*.*?\*/\s*\}", re.DOTALL)
_DOCSTRING = re.compile(r'"""[\s\S]*?"""')
_PY_COMENTARIO = re.compile(r"(^|\s)#.*$", re.MULTILINE)


def _sin_comentarios(contenido: str, sufijo: str) -> str:
    """Deja solo lo que puede terminar en pantalla."""
    if sufijo in {".ts", ".tsx"}:
        contenido = _JSX_COMENTARIO.sub(" ", contenido)
        contenido = _COMENTARIO_BLOQUE.sub(" ", contenido)
        return _COMENTARIO_LINEA.sub(" ", contenido)
    contenido = _DOCSTRING.sub(" ", contenido)
    return _PY_COMENTARIO.sub(" ", contenido)


def _fuentes_de_texto_visible():
    """Pantallas y componentes del frontend, y el catálogo del consentimiento."""
    for p in (_RAIZ / "frontend" / "src").rglob("*"):
        if p.is_file() and p.suffix in {".ts", ".tsx"} and ".test." not in p.name:
            yield p.relative_to(_RAIZ).as_posix(), p
    catalogo = _RAIZ / "backend" / "app" / "domain" / "consent_flow" / "text_catalog.py"
    if catalogo.exists():
        yield catalogo.relative_to(_RAIZ).as_posix(), catalogo


def test_ningun_texto_visible_cita_la_norma() -> None:
    """Si falla: sacá la cita del texto que se muestra, no del comentario."""
    culpables: list[str] = []
    for rel, p in _fuentes_de_texto_visible():
        if rel in _EXCEPCIONES:
            continue
        try:
            crudo = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "25.326" not in crudo and "25326" not in crudo:
            continue
        visible = _sin_comentarios(crudo, p.suffix)
        if any(pat.search(visible) for pat in _PATRONES):
            culpables.append(rel)
    assert not culpables, (
        "Estos archivos muestran la cita en texto visible:\n  "
        + "\n  ".join(sorted(culpables))
    )


@pytest.mark.parametrize(
    "codigo,sufijo,detecta",
    [
        ('const t = "dato sensible (Ley 25.326)";', ".ts", True),
        ("// dato sensible (Ley 25.326)", ".ts", False),
        ("{/* Ley 25.326 */}", ".tsx", False),
        ('texto = "conforme a la ley 25326"', ".py", True),
        ("# nota: Ley 25.326", ".py", False),
    ],
)
def test_distingue_texto_visible_de_comentario(codigo: str, sufijo: str, detecta: bool) -> None:
    """Sin estos casos, el test de arriba podría no mirar nada y pasar igual."""
    visible = _sin_comentarios(codigo, sufijo)
    encontrado = any(pat.search(visible) for pat in _PATRONES)
    assert encontrado is detecta
