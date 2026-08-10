"""C-75 / 0065: par de claves RS256 del Tool LTI (función pura, sin DB).

Verifica que `generar_par_rs256`:
  - devuelve una PEM privada RSA cargable,
  - devuelve un JWK público bien formado (kid/kty/use/alg + n/e),
  - el par firma-verifica de punta a punta (RS256): un JWT firmado con la privada
    valida contra el JWK público. Si esto falla, el JWKS que sirvamos no
    corresponde a la clave con que firmamos — Moodle rechazaría todo.
"""

from __future__ import annotations

import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from app.infrastructure.lti.keys import generar_par_rs256


def test_generar_par_rs256_pem_privada_cargable():
    pem_privada, _jwk, _kid = generar_par_rs256()
    key = load_pem_private_key(pem_privada.encode("utf-8"), password=None)
    assert key.key_size == 2048


def test_generar_par_rs256_jwk_publica_bien_formada():
    _pem, jwk_publica, kid = generar_par_rs256()
    assert jwk_publica["kty"] == "RSA"
    assert jwk_publica["use"] == "sig"
    assert jwk_publica["alg"] == "RS256"
    assert jwk_publica["kid"] == kid
    # Material público RSA presente (n = módulo, e = exponente).
    assert jwk_publica["n"]
    assert jwk_publica["e"]
    # La privada NO debe filtrarse en el JWK público.
    assert "d" not in jwk_publica


def test_generar_par_rs256_firma_y_verifica_end_to_end():
    pem_privada, jwk_publica, kid = generar_par_rs256()

    token = jwt.encode(
        {"sub": "alumno-1"},
        pem_privada,
        algorithm="RS256",
        headers={"kid": kid},
    )

    clave_publica = jwt.algorithms.RSAAlgorithm.from_jwk(jwk_publica)
    claims = jwt.decode(token, clave_publica, algorithms=["RS256"])
    assert claims["sub"] == "alumno-1"


def test_dos_generaciones_dan_kids_distintos():
    _p1, _j1, kid1 = generar_par_rs256()
    _p2, _j2, kid2 = generar_par_rs256()
    assert kid1 != kid2
