"""Tests del generador de codigo_matriculacion (C-70, tasks 2.1-2.3).

PUROS: el helper ``generar_codigo_libre`` recibe un callable ``persistir_con_codigo``
que simula el alta/rotación. Testeamos la orquestación del reintento ante colisión
(CodigoMatriculacionDuplicadoError → otro sufijo) SIN tocar la DB — el stub NO es un
mock de DB, es la frontera del helper (la DB real se cubre en los tests de service).
"""

from __future__ import annotations

import pytest

from app.application.exam_content.codigo_matriculacion import (
    LARGO_SUFIJO,
    componer_codigo,
    generar_codigo_libre,
    generar_sufijo,
    normalizar_codigo,
)
from app.domain.exam_content.errors import CodigoMatriculacionDuplicadoError

_ALFABETO = set("ABCDEFGHJKMNPQRSTUVWXYZ23456789")


# --- Generación de sufijo/código (sync, puras) -----------------------------


def test_sufijo_largo_y_alfabeto_sin_ambiguos():
    suf = generar_sufijo()
    assert len(suf) == LARGO_SUFIJO
    assert set(suf) <= _ALFABETO
    # Sin caracteres ambiguos.
    assert not (set(suf) & set("O0I1L"))


def test_componer_codigo_prefija_la_materia():
    cod = componer_codigo("PROG1", "AB23")
    assert cod == "PROG1-AB23"


def test_componer_codigo_autogenera_sufijo_si_falta():
    cod = componer_codigo("PROG1")
    assert cod.startswith("PROG1-")
    assert len(cod.split("-", 1)[1]) == LARGO_SUFIJO


def test_normalizar_solo_strip_no_cambia_case():
    # Decisión del owner: se guarda EXACTAMENTE como se tipeó (case-sensitive).
    assert normalizar_codigo("  PrOg1-Xy2Z  ") == "PrOg1-Xy2Z"


# --- Reintento ante colisión (async) ---------------------------------------


@pytest.mark.asyncio
async def test_genera_libre_al_primer_intento():
    intentos_vistos: list[str] = []

    async def _persistir(codigo: str) -> str:
        intentos_vistos.append(codigo)
        return f"ok:{codigo}"

    resultado = await generar_codigo_libre(_persistir, "PROG1")
    assert resultado.startswith("ok:PROG1-")
    assert len(intentos_vistos) == 1


@pytest.mark.asyncio
async def test_reintenta_ante_colision_y_usa_el_segundo_libre():
    # TRIANGULATE: la primera vez colisiona (23505), la segunda queda libre.
    intentos_vistos: list[str] = []

    async def _persistir(codigo: str) -> str:
        intentos_vistos.append(codigo)
        if len(intentos_vistos) == 1:
            raise CodigoMatriculacionDuplicadoError("colisión forzada")
        return f"ok:{codigo}"

    resultado = await generar_codigo_libre(_persistir, "PROG1")
    assert resultado.startswith("ok:PROG1-")
    assert len(intentos_vistos) == 2
    # Cada intento generó un sufijo (potencialmente distinto).
    assert all(c.startswith("PROG1-") for c in intentos_vistos)


@pytest.mark.asyncio
async def test_agota_intentos_y_eleva():
    async def _persistir(codigo: str) -> str:
        raise CodigoMatriculacionDuplicadoError("siempre colisiona")

    with pytest.raises(CodigoMatriculacionDuplicadoError):
        await generar_codigo_libre(_persistir, "PROG1", intentos=3)
