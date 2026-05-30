"""Tests de logica PURA del encadenamiento de hash del audit log (sin DB).

Verifica la capability ``append-only-audit-log`` (Requirement "Encadenamiento de
hash por entrada"): el ``hash_prev`` de cada entrada coincide con el hash de la
anterior y la cadena se valida extremo a extremo; una ruptura es detectable.

El rechazo de UPDATE/DELETE por el TRIGGER vive en la base y se prueba en
``test_db_invariants.py`` (``@pytest.mark.requires_stack``). Aqui se prueba el
algoritmo de hash encadenado, que es dominio puro.
"""

from __future__ import annotations

from app.domain.audit_chain import (
    GENESIS_HASH,
    AuditEntry,
    construir_cadena,
    hash_entrada,
    verificar_cadena,
)


def _entrada(actor: str, accion: str, hash_prev: str) -> AuditEntry:
    return AuditEntry(
        actor=actor,
        timestamp="2026-05-30T10:00:00Z",
        ip="10.0.0.1",
        user_agent="pytest",
        accion=accion,
        evidencia_id=None,
        proposito="test",
        hash_prev=hash_prev,
    )


def test_primera_entrada_encadena_al_genesis() -> None:
    cadena = construir_cadena([_entrada("a1", "login", "")])
    assert cadena[0].hash_prev == GENESIS_HASH


def test_hash_entrada_es_deterministico() -> None:
    e = _entrada("a1", "login", GENESIS_HASH)
    assert hash_entrada(e) == hash_entrada(e)


def test_cadena_valida_extremo_a_extremo() -> None:
    entradas = [
        _entrada("a1", "login", ""),
        _entrada("a2", "ver_evidencia", ""),
        _entrada("a3", "exportar", ""),
    ]
    cadena = construir_cadena(entradas)

    # Cada hash_prev coincide con el hash de la entrada anterior.
    for i in range(1, len(cadena)):
        assert cadena[i].hash_prev == hash_entrada(cadena[i - 1])

    assert verificar_cadena(cadena) is True


def test_ruptura_de_cadena_detectable() -> None:
    cadena = construir_cadena(
        [
            _entrada("a1", "login", ""),
            _entrada("a2", "ver_evidencia", ""),
            _entrada("a3", "exportar", ""),
        ]
    )
    # Manipula una entrada del medio: rompe el encadenamiento.
    cadena[1] = AuditEntry(
        actor="atacante",
        timestamp=cadena[1].timestamp,
        ip=cadena[1].ip,
        user_agent=cadena[1].user_agent,
        accion="borrar_evidencia",
        evidencia_id=cadena[1].evidencia_id,
        proposito=cadena[1].proposito,
        hash_prev=cadena[1].hash_prev,
    )
    assert verificar_cadena(cadena) is False


def test_insercion_fuera_de_banda_detectable() -> None:
    cadena = construir_cadena(
        [_entrada("a1", "login", ""), _entrada("a2", "exportar", "")]
    )
    # Inserta una entrada con hash_prev que no corresponde a la anterior.
    intrusa = _entrada("intruso", "exfiltrar", "hash_que_no_corresponde")
    cadena.insert(1, intrusa)
    assert verificar_cadena(cadena) is False
