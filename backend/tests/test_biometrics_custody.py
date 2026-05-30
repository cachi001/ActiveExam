"""Tests de custodia del clip + clave de sesion rotativa HMAC (C-09, logica pura).

RN-BIO-02 (clave rotativa HMAC), RN-BIO-07 (custodia del clip). El secreto maestro
se inyecta por parametro (nunca hardcodeado); la rotacion por epoca cambia la clave.
"""

from __future__ import annotations

from app.domain.biometrics import custody

_SECRETO = b"secreto-maestro-de-prueba-inyectado-por-vault"


def test_hash_clip_es_sha256_determinista() -> None:
    h1 = custody.hash_clip(b"clip-bytes")
    h2 = custody.hash_clip(b"clip-bytes")
    assert h1 == h2
    assert len(h1) == 64  # hex SHA-256
    assert custody.hash_clip(b"otro") != h1


def test_derivar_clave_sesion_es_determinista_por_sesion_y_epoca() -> None:
    k1 = custody.derivar_clave_sesion(secreto_maestro=_SECRETO, session_id="s1", epoca=0)
    k2 = custody.derivar_clave_sesion(secreto_maestro=_SECRETO, session_id="s1", epoca=0)
    assert k1 == k2
    assert len(k1) == 64


def test_clave_rota_con_la_epoca() -> None:
    k0 = custody.derivar_clave_sesion(secreto_maestro=_SECRETO, session_id="s1", epoca=0)
    k1 = custody.derivar_clave_sesion(secreto_maestro=_SECRETO, session_id="s1", epoca=1)
    assert k0 != k1  # rotacion: misma sesion, distinta epoca -> distinta clave


def test_claves_distintas_por_sesion() -> None:
    k_a = custody.derivar_clave_sesion(secreto_maestro=_SECRETO, session_id="a", epoca=0)
    k_b = custody.derivar_clave_sesion(secreto_maestro=_SECRETO, session_id="b", epoca=0)
    assert k_a != k_b


def test_secreto_maestro_vacio_falla() -> None:
    import pytest

    with pytest.raises(ValueError):
        custody.derivar_clave_sesion(secreto_maestro=b"", session_id="s1")


def test_firma_y_verificacion_del_clip() -> None:
    clave = custody.derivar_clave_sesion(secreto_maestro=_SECRETO, session_id="s1")
    clip_hash = custody.hash_clip(b"clip-de-verificacion")
    firma = custody.firmar_clip(clave_sesion=clave, clip_hash=clip_hash)
    assert custody.verificar_firma(
        clave_sesion=clave, mensaje=clip_hash.encode("utf-8"), firma=firma
    )


def test_firma_invalida_no_verifica() -> None:
    clave = custody.derivar_clave_sesion(secreto_maestro=_SECRETO, session_id="s1")
    assert not custody.verificar_firma(
        clave_sesion=clave, mensaje=b"mensaje", firma="00" * 32
    )


def test_firma_con_otra_clave_no_verifica() -> None:
    clave1 = custody.derivar_clave_sesion(secreto_maestro=_SECRETO, session_id="s1")
    clave2 = custody.derivar_clave_sesion(secreto_maestro=_SECRETO, session_id="s2")
    firma = custody.firmar(clave_sesion=clave1, mensaje=b"hola")
    assert not custody.verificar_firma(clave_sesion=clave2, mensaje=b"hola", firma=firma)
