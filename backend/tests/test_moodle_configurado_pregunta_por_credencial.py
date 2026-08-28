"""`moodle_configurado` se responde con la credencial, no con el objeto (27/8/2026).

Este test es de ARQUITECTURA: no ejercita un endpoint, vigila una regla que ya se
rompió una vez y que se rompe sin que nadie lo note.

Lo que pasó: `moodle_configurado = writeback_svc is not None`. El servicio se
construye SIEMPRE (para poder cargar el token desde la UI sin reiniciar), así que
esa cuenta daba true para siempre y el estado `sin_token` quedó inalcanzable. Sin
credencial la nota terminaba en `fallido`, y el docente leía "Falló el envío" de
un envío que nunca se intentó: sale a buscar un problema de red en vez de conectar
el campus.

La regla: quien calcule `moodle_configurado` tiene que preguntar por la credencial
vigente (`hay_credencial()`). La existencia del objeto no dice nada.

Ver `test_sin_token_era_inalcanzable.py` para el comportamiento en sí.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1] / "app"


def _valores_asignados(arbol: ast.AST):
    """Cada expresión que se le da a `moodle_configurado`, con su línea.

    Por AST y no por texto: la expresión ocupa varias líneas y una búsqueda por
    renglón no la ve entera (así se escapaba justamente la versión arreglada).
    """
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Assign):
            for destino in nodo.targets:
                if isinstance(destino, ast.Name) and destino.id == "moodle_configurado":
                    yield nodo.lineno, nodo.value
        elif isinstance(nodo, ast.keyword) and nodo.arg == "moodle_configurado":
            yield nodo.value.lineno, nodo.value


def _derivadas_del_servicio() -> list[tuple[Path, int, str]]:
    """Los lugares que CALCULAN el valor a partir del servicio de write-back.

    Pasarlo hacia adentro ya calculado (`moodle_configurado=moodle_configurado`)
    no es el defecto: el defecto es derivarlo del servicio sin mirar la credencial.
    """
    encontradas: list[tuple[Path, int, str]] = []
    for archivo in RAIZ.rglob("*.py"):
        # utf-8-sig: hay al menos un módulo guardado con BOM y `ast.parse` lo
        # rechaza como carácter no imprimible.
        arbol = ast.parse(archivo.read_text(encoding="utf-8-sig"))
        for nro, valor in _valores_asignados(arbol):
            fuente = ast.unparse(valor)
            if "writeback_svc" in fuente:
                encontradas.append((archivo, nro, fuente))
    return encontradas


def test_hay_al_menos_un_lugar_que_lo_calcula():
    # Si el nombre se renombra y nadie actualiza este test, el test pasaría vacío
    # y dejaría de vigilar nada. Esta guarda hace que falle en vez de mentir.
    assert _derivadas_del_servicio(), (
        "No se encontró ningún `moodle_configurado` derivado de `writeback_svc` en "
        "app/. Si se renombró, actualizá este test para que siga vigilando la regla."
    )


@pytest.mark.parametrize(
    ("archivo", "nro", "valor"),
    [pytest.param(a, n, v, id=f"{a.name}:{n}") for a, n, v in _derivadas_del_servicio()],
)
def test_ninguno_se_conforma_con_que_el_servicio_exista(archivo: Path, nro: int, valor: str):
    if "hay_credencial" in valor:
        return
    pytest.fail(
        f"{archivo}:{nro} calcula `moodle_configurado` como `{valor}` sin preguntar "
        "por la credencial vigente. El servicio se construye siempre, así que eso "
        "da true para siempre y deja `sin_token` inalcanzable. Usá "
        "`await writeback_svc.hay_credencial()`."
    )
