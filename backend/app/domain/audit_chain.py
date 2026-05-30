"""Logica PURA de la cadena de hash del audit log (cadena de custodia, DD-07).

PURA (regla dura monorepo-scaffolding / D1): sin SQLAlchemy ni infraestructura;
solo ``hashlib`` de la libreria estandar. Implementa el encadenamiento de hash
("blockchain rudimentaria", `04` Audit log): cada entrada lleva ``hash_prev``
igual al hash de la entrada anterior, formando una cadena validable a diario.

La INMUTABILIDAD (rechazo de UPDATE/DELETE) la garantiza el TRIGGER de la base
(migracion 002); aqui vive el algoritmo de hash y su verificacion extremo a
extremo, que es dominio puro y se testea sin DB.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

# Ancla de la cadena: el ``hash_prev`` de la primera entrada. Una cadena vacia
# encadena al genesis, de modo que toda entrada tiene un predecesor verificable.
GENESIS_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Entrada del audit log (`04` Audit log). Inmutable por diseno.

    ``hash_prev`` se completa al construir la cadena (``construir_cadena``); el
    valor entrante se ignora a favor del hash de la entrada anterior real.
    """

    actor: str
    timestamp: str
    ip: str
    user_agent: str
    accion: str
    evidencia_id: str | None
    proposito: str
    hash_prev: str = GENESIS_HASH


def hash_entrada(entrada: AuditEntry) -> str:
    """Hash SHA-256 determinista del contenido de una entrada, incluido su
    ``hash_prev`` (asi cualquier alteracion de una entrada previa propaga el
    cambio a toda la cadena posterior y la verificacion lo detecta)."""
    payload = "|".join(
        [
            entrada.actor,
            entrada.timestamp,
            entrada.ip,
            entrada.user_agent,
            entrada.accion,
            entrada.evidencia_id or "",
            entrada.proposito,
            entrada.hash_prev,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def construir_cadena(entradas: list[AuditEntry]) -> list[AuditEntry]:
    """Encadena una secuencia de entradas: fija el ``hash_prev`` de cada una al
    hash de la anterior (la primera al ``GENESIS_HASH``). Devuelve una lista
    nueva de entradas encadenadas, sin mutar la entrada original."""
    cadena: list[AuditEntry] = []
    prev = GENESIS_HASH
    for entrada in entradas:
        encadenada = replace(entrada, hash_prev=prev)
        cadena.append(encadenada)
        prev = hash_entrada(encadenada)
    return cadena


def verificar_cadena(cadena: list[AuditEntry]) -> bool:
    """Verifica la cadena extremo a extremo: el ``hash_prev`` de cada entrada
    debe coincidir con el hash de la anterior (y la primera con el genesis).
    Devuelve ``False`` ante cualquier ruptura (alteracion, insercion o borrado
    fuera de banda)."""
    prev = GENESIS_HASH
    for entrada in cadena:
        if entrada.hash_prev != prev:
            return False
        prev = hash_entrada(entrada)
    return True
