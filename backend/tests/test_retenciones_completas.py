"""Una fila muestra TODOS sus motivos de retención, no sólo el más grave.

Al examen le falta el destino en el campus: le falta para los 40 alumnos por
igual. Pero `_motivos_retencion` asignaba UN solo motivo por fila y, cuando la
sesión estaba anulada o en riesgo, hacía `continue` antes de mirar el destino.
Resultado en pantalla: tres filas decían "Falta el destino" y las otras tres no,
sobre el MISMO examen y la MISMA comisión. Se leía como un error de la pantalla.

Ahora se devuelven todos los motivos que aplican, en orden de importancia.
"""

from __future__ import annotations

from app.application.moodle.resultados_query import motivos_de_una_fila


def test_una_sesion_anulada_a_la_que_ademas_le_falta_el_destino_muestra_los_dos():
    assert motivos_de_una_fila(
        en_hold=True, anulada=True, sin_destino=True, sin_credencial=False
    ) == ["anulada", "sin_destino"]


def test_en_riesgo_y_sin_credencial_muestra_los_dos():
    assert motivos_de_una_fila(
        en_hold=True, anulada=False, sin_destino=False, sin_credencial=True
    ) == ["en_riesgo", "sin_credencial_docente"]


def test_lo_de_la_persona_va_primero():
    """El motivo de ESTA sesión pesa más que la config del examen: uno lo resuelve
    un revisor y el otro el administrador."""
    motivos = motivos_de_una_fila(
        en_hold=True, anulada=True, sin_destino=True, sin_credencial=True
    )
    assert motivos[0] == "anulada"
    assert set(motivos[1:]) == {"sin_destino", "sin_credencial_docente"}


def test_sin_hold_igual_se_reportan_los_del_examen():
    assert motivos_de_una_fila(
        en_hold=False, anulada=False, sin_destino=True, sin_credencial=False
    ) == ["sin_destino"]


def test_sin_nada_que_la_retenga_devuelve_vacio():
    assert motivos_de_una_fila(
        en_hold=False, anulada=False, sin_destino=False, sin_credencial=False
    ) == []


# ---------------------------------------------------------------------------
# `_motivos_retencion` pasó de devolver UN motivo a devolver la lista completa.
# Ese cambio rompió TRES consumidores que lo trataban como un string, y cada uno
# apareció por separado: uno tumbaba el marcado a mano y otro la pantalla de
# notas del ALUMNO (`unhashable type: 'list'`). Acá quedan los tres juntos para
# que el próximo cambio de forma los agarre de una.
# ---------------------------------------------------------------------------

from datetime import datetime, timezone

from app.application.moodle.marcado_manual import puede_marcarse_cargada
from app.domain.exam_content.resultado_nota import resultado_de
from app.domain.exam_content.visibilidad import nota_visible_para_alumno


def test_el_marcado_a_mano_acepta_la_lista():
    assert puede_marcarse_cargada(["sin_destino", "sin_credencial_docente"]) is True
    assert puede_marcarse_cargada(["en_riesgo", "sin_destino"]) is False


def test_la_visibilidad_de_la_nota_acepta_la_lista():
    ahora = datetime(2026, 8, 28, tzinfo=timezone.utc)
    # Con `anulada` en la lista la nota se oculta, esté donde esté en el orden.
    assert (
        nota_visible_para_alumno(
            mostrar_nota="inmediata",
            cierre=None,
            ahora=ahora,
            retenido_por=["anulada", "sin_destino"],
        )
        is False
    )
    assert (
        nota_visible_para_alumno(
            mostrar_nota="inmediata",
            cierre=None,
            ahora=ahora,
            retenido_por=["sin_destino"],
        )
        is True
    )


def test_el_resultado_se_calcula_con_el_motivo_principal():
    """`resultado_de` recibe el PRIMERO de la lista, que es el de la sesión."""
    motivos = motivos_de_una_fila(
        en_hold=True, anulada=True, sin_destino=True, sin_credencial=False
    )
    assert resultado_de(aprobado=True, nota=78.0, retenido_por=motivos[0]).value == "anulada"
