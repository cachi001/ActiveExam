"""Tests unitarios de calcular_score() — sin DB, sin red.

Verifica pesos por severidad (fallback, RN-GLB-03), score cero, suma de
multiples eventos y severidades desconocidas. L2.5: el score solo prioriza la
revision humana, nunca sanciona.

Las severidades canonicas son ``baja``, ``media``, ``alta``, ``critica``
(alineadas con ``evento_score_config`` y ``app/domain/scoring/risk_score.py``);
``baseline`` no es un evento y no suma. Los pesos del fallback son el centro de
los rangos institucionales (SEVERITY_RANGES).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.proctoring.scoring import (
    PESOS_SEVERIDAD,
    calcular_score,
    construir_config_snapshot,
    desactivados_de_snapshot,
    pesos_de_snapshot,
    umbral_de_snapshot,
)


@dataclass
class _FakeEvento:
    """Evento fake duck-typed para tests unitarios (sin DB)."""

    severidad: str
    tipo: str = ""


def test_score_cero_sin_eventos() -> None:
    """Score de lista vacia es 0."""
    assert calcular_score([]) == 0


def test_score_baja() -> None:
    """Un evento 'baja' → peso 5 (fallback, centro del rango [1-10])."""
    assert calcular_score([_FakeEvento("baja")]) == 5


def test_score_media() -> None:
    """Un evento 'media' → peso 20 (fallback, centro del rango [11-30])."""
    assert calcular_score([_FakeEvento("media")]) == 20


def test_score_alta() -> None:
    """Un evento 'alta' → peso 45 (fallback, centro del rango [31-60])."""
    assert calcular_score([_FakeEvento("alta")]) == 45


def test_score_critica() -> None:
    """Un evento 'critica' → peso 80 (fallback, centro del rango [61-100])."""
    assert calcular_score([_FakeEvento("critica")]) == 80


def test_score_suma_multiples() -> None:
    """Score de multiples eventos suma sus pesos (sin alcanzar el cap de 100)."""
    eventos = [
        _FakeEvento("baja"),   # 5
        _FakeEvento("media"),  # 20
        _FakeEvento("alta"),   # 45
    ]
    assert calcular_score(eventos) == 70


def test_score_baseline_no_suma() -> None:
    """baseline no es un evento (piso 0 del score)."""
    assert calcular_score([_FakeEvento("baseline")]) == 0


def test_score_severidad_desconocida_es_cero() -> None:
    """Severidad no mapeada no suma (evita error silencioso)."""
    assert calcular_score([_FakeEvento("ultra")]) == 0
    assert calcular_score([_FakeEvento("")]) == 0


def test_pesos_fallback_alineados_con_rangos_institucionales() -> None:
    """El fallback por severidad debe estar dentro del rango institucional
    (SEVERITY_RANGES) de la severidad correspondiente, idealmente en el centro."""
    assert 1 <= PESOS_SEVERIDAD["baja"] <= 10
    assert 11 <= PESOS_SEVERIDAD["media"] <= 30
    assert 31 <= PESOS_SEVERIDAD["alta"] <= 60


# ---------------------------------------------------------------------------
# Snapshot de config al crear la sesion (migration 0083) — RED -> GREEN -> TRIANGULATE.
#
# Un cambio de umbral/pesos en Configuración no debe afectar retroactivamente
# una sesión que ya arrancó: la sesión puntúa con la foto tomada al crearla, no
# con la config vigente en el momento en que se la mira o se cierra.
# ---------------------------------------------------------------------------


def test_construir_snapshot_forma_el_dict_json_safe() -> None:
    snap = construir_config_snapshot(
        umbral_cola_revision=80,
        pesos_por_tipo={"rostro_ausente": 20},
        tipos_desactivados=frozenset({"copiar_pegar"}),
    )
    assert snap == {
        "umbral_cola_revision": 80,
        "scoring_weights": {"rostro_ausente": 20},
        "scoring_desactivados": ["copiar_pegar"],
    }


def test_pesos_de_snapshot_usa_la_foto_cuando_existe() -> None:
    """Caso 1: sesión CON snapshot → manda la foto, no los pesos vivos."""
    snap = construir_config_snapshot(
        umbral_cola_revision=70, pesos_por_tipo={"rostro_ausente": 20}, tipos_desactivados=None,
    )
    pesos_vivos_cambiados = {"rostro_ausente": 99}  # admin cambió el peso DESPUÉS
    assert pesos_de_snapshot(snap, pesos_vivos=pesos_vivos_cambiados) == {"rostro_ausente": 20}


def test_pesos_de_snapshot_cae_a_vivos_sin_foto() -> None:
    """Caso 2: sesión SIN snapshot (pre-migración o degradación) → cae a los vivos."""
    assert pesos_de_snapshot(None, pesos_vivos={"rostro_ausente": 99}) == {"rostro_ausente": 99}


def test_desactivados_de_snapshot_usa_la_foto_cuando_existe() -> None:
    snap = construir_config_snapshot(
        umbral_cola_revision=70, pesos_por_tipo={}, tipos_desactivados=frozenset({"copiar_pegar"}),
    )
    assert desactivados_de_snapshot(snap, desactivados_vivos=frozenset({"otro_tipo"})) == frozenset(
        {"copiar_pegar"}
    )


def test_desactivados_de_snapshot_cae_a_vivos_sin_foto() -> None:
    assert desactivados_de_snapshot(None, desactivados_vivos=frozenset({"otro_tipo"})) == frozenset(
        {"otro_tipo"}
    )


def test_umbral_de_snapshot_usa_la_foto_cuando_existe() -> None:
    """El caso concreto que reportó el usuario: si el umbral era 20 al rendir y
    el admin lo sube a 25 DURANTE el examen, esa sesión sigue evaluándose con 20."""
    snap = construir_config_snapshot(umbral_cola_revision=20, pesos_por_tipo={}, tipos_desactivados=None)
    umbral_vivo_cambiado = 25
    assert umbral_de_snapshot(snap, umbral_vivo=umbral_vivo_cambiado) == 20


def test_umbral_de_snapshot_cae_a_vivo_sin_foto() -> None:
    assert umbral_de_snapshot(None, umbral_vivo=70) == 70
    assert 61 <= PESOS_SEVERIDAD["critica"] <= 100


def test_score_solo_criticas_topa_en_cap() -> None:
    """3 eventos criticos (3 * 80 = 240) superan el cap → score topa en 100 (0..100)."""
    eventos = [_FakeEvento("critica")] * 3
    assert calcular_score(eventos) == 100
