"""C-72 §6 — Candado direccional de configuración (dominio puro).

Corre SIN base de datos. El candado post-rendición: CONGELADO DURO (cualquier
cambio → bloqueado) y DIRECCIONAL — `cierre` solo extender, `intentos_permitidos`
solo aumentar, `revision_habilitada` solo habilitar, `mostrar_nota` solo mostrar
antes (§18: publicar/ocultar resultados también es direccional, no libre).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.exam_content.config import cambios_bloqueados


def _dt(dia: int) -> datetime:
    return datetime(2026, 7, dia, 12, 0, tzinfo=timezone.utc)


_VIGENTE = {
    "nota_maxima": 100.0,
    "nota_aprobacion": 60.0,
    "tiempo_limite_min": 40,
    "mezclar_preguntas": True,
    "apertura": _dt(10),
    "cierre": _dt(20),
    "intentos_permitidos": 1,
    "mostrar_nota": "al_cerrar",
    "revision_habilitada": False,
}


# --- 6.1 congelado duro ---

def test_congelado_duro_siempre_bloqueado_si_rendido():
    bloq = cambios_bloqueados(
        cambios={"nota_maxima": 90.0}, vigente=_VIGENTE, ya_rendido=True
    )
    assert "nota_maxima" in bloq


# --- 6.2 cierre direccional (solo extender) ---

def test_cierre_posterior_permitido():
    # extender la ventana (cierre más tarde que el vigente día 20) → permitido
    bloq = cambios_bloqueados(
        cambios={"cierre": _dt(25)}, vigente=_VIGENTE, ya_rendido=True
    )
    assert "cierre" not in bloq


def test_cierre_anterior_bloqueado():
    # acortar la ventana (cierre antes que el vigente) → bloqueado
    bloq = cambios_bloqueados(
        cambios={"cierre": _dt(15)}, vigente=_VIGENTE, ya_rendido=True
    )
    assert "cierre" in bloq


# --- 6.3 intentos_permitidos direccional (solo aumentar) ---

def test_intentos_mayor_permitido():
    bloq = cambios_bloqueados(
        cambios={"intentos_permitidos": 3}, vigente=_VIGENTE, ya_rendido=True
    )
    assert "intentos_permitidos" not in bloq


def test_intentos_menor_bloqueado():
    vigente = {**_VIGENTE, "intentos_permitidos": 3}
    bloq = cambios_bloqueados(
        cambios={"intentos_permitidos": 1}, vigente=vigente, ya_rendido=True
    )
    assert "intentos_permitidos" in bloq


# --- 6.4 / §18 publicación DIRECCIONAL (solo la dirección generosa) ---

def test_habilitar_revision_permitido():
    # false→true: darle la revisión al alumno es generoso → permitido
    bloq = cambios_bloqueados(
        cambios={"revision_habilitada": True}, vigente=_VIGENTE, ya_rendido=True
    )
    assert "revision_habilitada" not in bloq


def test_quitar_revision_bloqueado():
    # true→false: sacarle la revisión que iba a ver → bloqueado
    vigente = {**_VIGENTE, "revision_habilitada": True}
    bloq = cambios_bloqueados(
        cambios={"revision_habilitada": False}, vigente=vigente, ya_rendido=True
    )
    assert "revision_habilitada" in bloq


def test_mostrar_nota_antes_permitido():
    # al_cerrar→inmediata: mostrar la nota antes es generoso → permitido
    bloq = cambios_bloqueados(
        cambios={"mostrar_nota": "inmediata"}, vigente=_VIGENTE, ya_rendido=True
    )
    assert "mostrar_nota" not in bloq


def test_ocultar_nota_bloqueado():
    # inmediata→al_cerrar: ocultar la nota que se iba a ver ya → bloqueado
    vigente = {**_VIGENTE, "mostrar_nota": "inmediata"}
    bloq = cambios_bloqueados(
        cambios={"mostrar_nota": "al_cerrar"}, vigente=vigente, ya_rendido=True
    )
    assert "mostrar_nota" in bloq


def test_publicacion_direccional_sin_rendir_permitido():
    # sin rendir, cualquier dirección se permite
    vigente = {**_VIGENTE, "revision_habilitada": True, "mostrar_nota": "inmediata"}
    bloq = cambios_bloqueados(
        cambios={"revision_habilitada": False, "mostrar_nota": "al_cerrar"},
        vigente=vigente,
        ya_rendido=False,
    )
    assert bloq == frozenset()


# --- 6.5 sin rendir → nada se bloquea ---

def test_sin_rendir_todo_permitido():
    bloq = cambios_bloqueados(
        cambios={"nota_maxima": 90.0, "cierre": _dt(15), "intentos_permitidos": 1},
        vigente={**_VIGENTE, "intentos_permitidos": 3},
        ya_rendido=False,
    )
    assert bloq == frozenset()
