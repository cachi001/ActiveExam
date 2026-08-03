"""Un tipo de evento DESACTIVADO en Configuración → Scoring debe pesar 0 server-side.

BUG que clavan estos tests: al desactivar un tipo (``evento_score_config.activo =
false``), el tipo sale del mapa de pesos vivos. Ambos motores de score trataban esa
ausencia como "no hay config" y caían al fallback POR SEVERIDAD (RN-GLB-03), así
que un ``copiar_pegar`` desactivado seguía sumando 20 puntos server-side — mientras
el cliente, siguiendo el contrato documentado del router de scoring ("tipos con
activo=False NO aparecen en el mapa: el cliente trata su peso como 0"), lo sumaba
como 0. Score del cliente y score del servidor divergían, y "desactivar" no
desactivaba nada donde importa.

Contrato: hay TRES estados, no dos.
- Tipo APAGADO (fila con ``activo=False``) → pesa 0.
- Tipo ACTIVO → su peso configurado.
- Tipo DESCONOCIDO (sin fila) o config no disponible → fallback por severidad
  (RN-GLB-03), porque un detector nuevo sin sembrar no puede valer 0 en silencio.

L2.5: el score solo PRIORIZA la revisión humana (RN-SC-01).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.proctoring.scoring import calcular_score
from app.domain.scoring.risk_score import EventoScore, PesosScore, peso_evento


@dataclass
class _Ev:
    """Evento duck-typed como los que llegan de ProctoringEventModel."""

    tipo: str
    severidad: str


# --- Motor on-the-fly (vista del proctor / stats) ---------------------------


def test_tipo_desactivado_no_suma() -> None:
    """copiar_pegar apagado por el admin → 0, no 20 por severidad."""
    pesos = {"cambio_pestana": 20, "multiples_rostros": 50}
    eventos = [_Ev("copiar_pegar", "media"), _Ev("copiar_pegar", "media")]
    score = calcular_score(
        eventos, pesos_por_tipo=pesos, tipos_desactivados=frozenset({"copiar_pegar"})
    )
    assert score == 0


def test_tipo_desconocido_sigue_degradando_por_severidad() -> None:
    """Un detector NUEVO (sin fila en la config) no puede valer 0 en silencio."""
    pesos = {"cambio_pestana": 20}
    eventos = [_Ev("detector_nuevo", "media")]
    score = calcular_score(
        eventos, pesos_por_tipo=pesos, tipos_desactivados=frozenset({"copiar_pegar"})
    )
    assert score == 20


def test_tipos_activos_siguen_sumando_su_peso_configurado() -> None:
    pesos = {"cambio_pestana": 30, "multiples_rostros": 50}
    eventos = [_Ev("cambio_pestana", "media"), _Ev("multiples_rostros", "alta")]
    assert calcular_score(eventos, pesos_por_tipo=pesos) == 80


def test_mezcla_activo_y_desactivado_solo_cuenta_el_activo() -> None:
    pesos = {"cambio_pestana": 30}
    eventos = [
        _Ev("cambio_pestana", "media"),
        _Ev("copiar_pegar", "media"),
        _Ev("copiar_pegar", "media"),
    ]
    score = calcular_score(
        eventos, pesos_por_tipo=pesos, tipos_desactivados=frozenset({"copiar_pegar"})
    )
    assert score == 30


def test_sin_config_viva_sigue_el_fallback_por_severidad() -> None:
    """Red de seguridad intacta: sin mapa (None) se puntúa por severidad."""
    eventos = [_Ev("copiar_pegar", "media"), _Ev("perdida_de_foco", "baja")]
    assert calcular_score(eventos, pesos_por_tipo=None) == 25


def test_mapa_vacio_tambien_degrada_por_severidad() -> None:
    """Mapa vacío = config no disponible: degrada por severidad, no cero.

    Si la carga de config fallara y devolviera {}, poner TODO en 0 apagaría el
    score en silencio."""
    eventos = [_Ev("copiar_pegar", "media")]
    assert calcular_score(eventos, pesos_por_tipo={}) == 20


# --- Motor de cierre (score persistido) -------------------------------------


def test_cierre_tipo_desactivado_pesa_cero() -> None:
    pesos = PesosScore(
        por_tipo={"cambio_pestana": 30.0}, desactivados=frozenset({"copiar_pegar"})
    )
    ev = EventoScore(tipo="copiar_pegar", severidad="media", ts_ms=0)
    assert peso_evento(ev, pesos) == 0.0


def test_cierre_tipo_desconocido_degrada_por_severidad() -> None:
    """Sin fila en la config (detector nuevo) → fallback, no 0."""
    pesos = PesosScore(
        por_tipo={"cambio_pestana": 30.0}, desactivados=frozenset({"copiar_pegar"})
    )
    ev = EventoScore(tipo="detector_nuevo", severidad="media", ts_ms=0)
    assert peso_evento(ev, pesos) > 0.0


def test_cierre_tipo_activo_usa_su_peso() -> None:
    pesos = PesosScore(por_tipo={"cambio_pestana": 30.0})
    ev = EventoScore(tipo="cambio_pestana", severidad="media", ts_ms=0)
    assert peso_evento(ev, pesos) == 30.0


def test_cierre_sin_config_viva_degrada_por_severidad() -> None:
    """por_tipo None → red de seguridad por severidad (RN-GLB-03)."""
    ev = EventoScore(tipo="copiar_pegar", severidad="media", ts_ms=0)
    assert peso_evento(ev, PesosScore()) > 0.0


def test_cierre_mapa_vacio_degrada_por_severidad() -> None:
    ev = EventoScore(tipo="copiar_pegar", severidad="media", ts_ms=0)
    assert peso_evento(ev, PesosScore(por_tipo={})) > 0.0
