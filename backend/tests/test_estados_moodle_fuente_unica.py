"""Los estados de la nota tienen UNA fuente: el backend.

El frontend repetía a mano la lista de estados y sus etiquetas (el badge de la
tabla por un lado, el desplegable del filtro por otro). Cuando c-78 D14 agregó
'manual' ("cargada a mano en el campus"), el badge lo aprendió y el filtro no, así
que el estado se podía ver pero no filtrar; y el mapa del backend se quedó con los
cuatro viejos, de modo que en los reportes salía como "Manual" pelado en vez de
"Cargada a mano".

El test que decía cuidar ese desfasaje afirmaba el conjunto viejo *literal*
(`== {"pendiente", "enviado", "fallido", "sin_token"}`), o sea que pasaba
justamente porque nadie había agregado el quinto. Un test que congela la lista
vieja no detecta que apareció uno nuevo: acá se deriva del enum real.
"""

from __future__ import annotations

from app.application.moodle.resultados_query import ESTADO_MANUAL, ESTADO_SIN_TOKEN
from app.application.moodle.writeback_service import WritebackEstado
from app.application.stats.labels import (
    ESTADOS_MOODLE,
    ETIQUETA_ESTADO_MOODLE,
    etiqueta_estado_moodle,
)


def _estados_reales() -> set[str]:
    """Todo lo que `estado_moodle` puede valer de cara al admin."""
    return {e.value for e in WritebackEstado} | {ESTADO_SIN_TOKEN, ESTADO_MANUAL}


def test_el_mapa_cubre_todos_los_estados_que_existen():
    """Se deriva del enum: agregar un estado sin etiqueta rompe el test."""
    assert set(ETIQUETA_ESTADO_MOODLE) == _estados_reales()


def test_manual_tiene_su_etiqueta_y_no_cae_al_fallback():
    """'manual' no puede mostrarse como "Manual" humanizado."""
    assert etiqueta_estado_moodle("manual") == "Cargada a mano"


def test_ninguna_etiqueta_se_ve_como_codigo_tecnico():
    for estado, etiqueta in ETIQUETA_ESTADO_MOODLE.items():
        assert "_" not in etiqueta, f"{estado} se muestra como código: {etiqueta}"
        assert etiqueta[:1].isupper(), f"{estado} no arranca en mayúscula: {etiqueta}"


def test_estados_moodle_expone_valor_etiqueta_y_tono_de_cada_uno():
    """Lo que consume el frontend: sin esto tendría que elegir el color a mano."""
    assert [e["valor"] for e in ESTADOS_MOODLE] == list(ETIQUETA_ESTADO_MOODLE)
    for e in ESTADOS_MOODLE:
        assert e["etiqueta"] == ETIQUETA_ESTADO_MOODLE[e["valor"]]
        assert e["tono"] in {"warning", "success", "error", "neutral", "primary"}


def test_enviado_y_manual_no_comparten_tono():
    """Verde es "el campus lo confirmó". "Alguien dice que lo cargó" no puede
    verse igual: es la distinción que importa cuando hay un reclamo."""
    tonos = {e["valor"]: e["tono"] for e in ESTADOS_MOODLE}
    assert tonos["enviado"] != tonos["manual"]


# ---------------------------------------------------------------------------
# El candado: que nadie vuelva a escribir estas etiquetas en otro lado.
#
# El export tenía su propia copia con textos DISTINTOS ("Sin conexión al campus"
# donde la pantalla decía "Sin token"), y nadie se enteró hasta abrir el archivo
# al lado de la pantalla. Una segunda copia no falla: divergen en silencio.
# ---------------------------------------------------------------------------

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "app"

#: Donde VIVEN las etiquetas. Es el único archivo autorizado a escribirlas.
FUENTE = RAIZ / "domain" / "exam_content" / "estado_entrega.py"


def test_las_etiquetas_solo_estan_escritas_en_la_fuente():
    # Sólo las DISTINTIVAS (más de una palabra). "Pendiente" o "Enviado" sueltas
    # también son etiquetas de las decisiones de revisión y de otros dominios:
    # encontrarlas en otro archivo no prueba que alguien copió ESTAS, y el test
    # empezaba a fallar por código que no tiene nada que ver.
    etiquetas = {e for e in ETIQUETA_ESTADO_MOODLE.values() if " " in e}
    culpables: list[str] = []
    for archivo in RAIZ.rglob("*.py"):
        if archivo == FUENTE:
            continue
        try:
            arbol = ast.parse(archivo.read_text(encoding="utf-8-sig"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and nodo.value in etiquetas:
                culpables.append(f"{archivo.relative_to(RAIZ)}:{nodo.lineno} → {nodo.value!r}")

    assert not culpables, (
        "Estas etiquetas están escritas fuera de `EstadoEntregaNota`: "
        + "; ".join(culpables)
        + ". Una segunda copia no falla, diverge en silencio: usá "
        "`etiqueta_estado_entrega()` en vez de repetir el texto."
    )
