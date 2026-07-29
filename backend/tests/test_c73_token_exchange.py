"""Canje contraseña→token contra Moodle (C-73 §10.2).

Este módulo es el ÚNICO lugar del sistema que ve una contraseña de campus. El
contrato que se clava acá es doble:

1. Traduce cada respuesta de Moodle al error correcto (las credenciales malas y el
   servicio no habilitado son problemas distintos, con arreglos distintos: uno lo
   resuelve el docente, el otro el admin del campus).
2. La contraseña NO sale: ni en el resultado, ni en los mensajes de error.

No hay DB acá: es lógica de traducción HTTP pura. El transporte se sustituye con un
`httpx.MockTransport` (NO se mockea una base de datos).
"""

from __future__ import annotations

import httpx
import pytest

from app.application.moodle.token_exchange import (
    CredencialesInvalidasError,
    ServicioNoHabilitadoError,
    TokenExchangeError,
    canjear_password_por_token,
)

_PASSWORD = "sup3r-secreta-del-campus"  # noqa: S105  (valor falso, solo para el test)


def _cliente(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _canjear(handler, **kwargs):
    async with _cliente(handler) as c:
        return await canjear_password_por_token(
            base_url="https://campus.test",
            username="jperez",
            password=_PASSWORD,
            service_shortname="activeexam",
            client=c,
            **kwargs,
        )


@pytest.mark.asyncio
async def test_devuelve_el_token_cuando_moodle_lo_emite():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/login/token.php"
        # El service viaja: es lo que ACOTA el token a nuestras funciones.
        assert b"service=activeexam" in request.content
        return httpx.Response(200, json={"token": "abc123def456"})

    obtenido = await _canjear(handler)
    assert obtenido.token == "abc123def456"


@pytest.mark.asyncio
async def test_invalidlogin_es_credenciales_invalidas():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"error": "Acceso inválido", "errorcode": "invalidlogin"}
        )

    with pytest.raises(CredencialesInvalidasError):
        await _canjear(handler)


@pytest.mark.asyncio
async def test_servicio_no_habilitado_se_distingue_de_credenciales_malas():
    """Se separan porque el arreglo es distinto: acá el admin del campus autoriza."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"error": "Servicio no disponible", "errorcode": "accessexception"},
        )

    with pytest.raises(ServicioNoHabilitadoError):
        await _canjear(handler)


@pytest.mark.asyncio
async def test_la_password_no_aparece_en_ningun_mensaje_de_error():
    """Guardrail: un error con la contraseña adentro termina en logs y tickets."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"error": "Acceso inválido", "errorcode": "invalidlogin"}
        )

    with pytest.raises(TokenExchangeError) as exc:
        await _canjear(handler)
    assert _PASSWORD not in str(exc.value)
    assert _PASSWORD not in repr(exc.value)


@pytest.mark.asyncio
async def test_error_de_red_no_filtra_la_password():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin ruta al host")

    with pytest.raises(TokenExchangeError) as exc:
        await _canjear(handler)
    assert _PASSWORD not in str(exc.value)


@pytest.mark.asyncio
async def test_respuesta_sin_token_es_error_explicito():
    """200 sin token y sin error: no se puede seguir como si hubiera credencial."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"privatetoken": "x"})

    with pytest.raises(TokenExchangeError):
        await _canjear(handler)


@pytest.mark.asyncio
async def test_respuesta_ilegible_es_error_explicito():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>portal caído</html>")

    with pytest.raises(TokenExchangeError):
        await _canjear(handler)


@pytest.mark.asyncio
async def test_falta_service_shortname_falla_antes_de_salir_a_la_red():
    """Sin service no hay token acotado: mejor fallar acá que pedir uno sin límites."""
    llamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        llamadas.append(request)
        return httpx.Response(200, json={"token": "no-deberia-llegar"})

    async with _cliente(handler) as c:
        with pytest.raises(TokenExchangeError):
            await canjear_password_por_token(
                base_url="https://campus.test",
                username="jperez",
                password=_PASSWORD,
                service_shortname="",
                client=c,
            )
    assert llamadas == []
