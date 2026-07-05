"""Tests de normalizacion de IP del audit log (robustez del INSERT en columna INET).

Contexto: el audit log guarda `request.client.host` en una columna Postgres INET.
Detras de nginx es una IP real, pero con el TestClient de FastAPI (host
'testclient'), un proxy mal configurado o un socket unix puede NO ser una IP.
Un valor no-IP aborta el INSERT (asyncpg DataError) y tumbaria la accion
auditada. `_normalizar_ip` coerciona cualquier host no-IP a None para que la
entrada del audit log se registre igual (con ip=NULL) en vez de perderse.

Test puro (sin DB): valida solo la funcion de normalizacion.
"""

from __future__ import annotations

import pytest

from app.infrastructure.persistence.repositories.audit_log import _normalizar_ip


class TestNormalizarIp:
    def test_ipv4_valida_se_conserva(self) -> None:
        assert _normalizar_ip("192.168.1.10") == "192.168.1.10"

    def test_ipv6_valida_se_conserva(self) -> None:
        assert _normalizar_ip("2001:db8::1") == "2001:db8::1"

    def test_localhost_ipv4_se_conserva(self) -> None:
        assert _normalizar_ip("127.0.0.1") == "127.0.0.1"

    def test_host_testclient_se_normaliza_a_none(self) -> None:
        # El caso que rompia: TestClient de FastAPI usa el host literal 'testclient'.
        assert _normalizar_ip("testclient") is None

    def test_string_arbitrario_no_ip_a_none(self) -> None:
        assert _normalizar_ip("no-es-una-ip") is None

    def test_ipv4_fuera_de_rango_a_none(self) -> None:
        assert _normalizar_ip("999.999.999.999") is None

    @pytest.mark.parametrize("vacio", ["", None])
    def test_vacio_o_none_a_none(self, vacio: str | None) -> None:
        assert _normalizar_ip(vacio) is None
