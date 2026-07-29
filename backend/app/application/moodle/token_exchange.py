"""Canje de contrasena por token de Web Services de Moodle (C-73 §10.2).

POR QUE EXISTE ESTE MODULO:
  Moodle NO acepta usuario/contrasena en un web service. La unica credencial que
  `core_grades_update_grades` acepta es un `wstoken`. La contrasena sirve para UNA
  sola cosa: pedir un token en `login/token.php`.

  Entonces el flujo es: el docente escribe usuario y contrasena UNA vez -> se canjean
  aca por un token -> se guarda el TOKEN cifrado -> la contrasena se descarta.

  Este modulo es el unico lugar del sistema que ve una contrasena de campus, y su
  contrato es no dejarla salir: no la loguea, no la devuelve, no la persiste y no la
  incluye en los mensajes de error.

EL TOKEN QUEDA ACOTADO:
  `login/token.php` recibe `service=<shortname>`. Lo que devuelve NO es "la cuenta
  entera" de la persona: es un token que solo puede llamar a las funciones que ese
  servicio externo declara. Si el servicio expone unicamente escritura de notas, eso
  es todo lo que ese token puede hacer, aunque se filtre.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx


class TokenExchangeError(Exception):
    """Falla del canje. Su ``str`` NUNCA incluye la contrasena."""


class CredencialesInvalidasError(TokenExchangeError):
    """Moodle rechazo usuario/contrasena (`invalidlogin`)."""


class ServicioNoHabilitadoError(TokenExchangeError):
    """El usuario no puede usar ese servicio externo, o el servicio no existe.

    Caso tipico y facil de diagnosticar mal: el servicio esta configurado como "solo
    usuarios autorizados" y el docente no esta en la lista. La contrasena es correcta;
    lo que falta es habilitacion en el campus."""


@dataclass(frozen=True, slots=True)
class TokenObtenido:
    """Resultado del canje. ``token`` en claro: cifrarlo antes de persistir."""

    token: str
    #: `private_token` de Moodle, si vino. No lo usamos; se ignora a proposito.
    tiene_private_token: bool = False


# Moodle contesta 200 con un cuerpo {"error": ..., "errorcode": ...} incluso cuando
# fallo: el status HTTP no alcanza para saber si salio bien.
_ERRORES_DE_CREDENCIAL = {"invalidlogin", "invalidaccount"}
_ERRORES_DE_SERVICIO = {
    "enabledwsdescription",
    "servicenotavailable",
    "accessexception",
    "invalidparameter",
    # Credenciales CORRECTAS, pero el campus no deja que ese usuario emita un token:
    # le falta `moodle/webservice:createtoken` EN CONTEXTO SISTEMA, o el servicio
    # esta restringido a usuarios autorizados y no esta en la lista. Verificado en
    # campustest: un profesor con el rol asignado A NIVEL DE CURSO recibe esto,
    # porque la capacidad se evalua en el contexto SISTEMA, no en el del curso.
    "cannotcreatetoken",
}


async def canjear_password_por_token(
    *,
    base_url: str,
    username: str,
    password: str,
    service_shortname: str,
    timeout: float = 10.0,
    client: httpx.AsyncClient | None = None,
) -> TokenObtenido:
    """Cambia usuario+contrasena por un `wstoken` acotado a ``service_shortname``.

    La contrasena se usa SOLO en el cuerpo de este POST y no sale de esta funcion.

    Lanza ``CredencialesInvalidasError`` si Moodle rechaza la identidad,
    ``ServicioNoHabilitadoError`` si el problema es el servicio externo (tipicamente
    lista blanca de usuarios autorizados), y ``TokenExchangeError`` para el resto
    (red, respuesta ilegible, cuerpo inesperado).
    """
    if not base_url:
        raise TokenExchangeError("Falta la URL del campus.")
    if not service_shortname:
        raise TokenExchangeError(
            "Falta el nombre del servicio externo del campus (service shortname)."
        )
    if not username or not password:
        raise CredencialesInvalidasError("Usuario y contraseña son obligatorios.")

    url = f"{base_url.rstrip('/')}/login/token.php"
    data = {
        "username": username,
        "password": password,
        "service": service_shortname,
    }

    propio = client is None
    http = client or httpx.AsyncClient(timeout=timeout)
    try:
        try:
            response = await http.post(url, data=data)
        except Exception as exc:
            # El mensaje de httpx puede incluir la URL pero nunca el body: aun asi se
            # reescribe para no arrastrar nada del intento.
            raise TokenExchangeError(
                f"No se pudo contactar al campus: {type(exc).__name__}"
            ) from None
    finally:
        if propio:
            await http.aclose()

    if response.status_code >= 400:
        raise TokenExchangeError(f"El campus devolvió HTTP {response.status_code}.")

    try:
        body = response.json()
    except Exception:
        raise TokenExchangeError("El campus devolvió una respuesta ilegible.") from None

    if not isinstance(body, dict):
        raise TokenExchangeError("El campus devolvió una respuesta inesperada.")

    if "error" in body or "errorcode" in body:
        codigo = str(body.get("errorcode") or "").lower()
        if codigo in _ERRORES_DE_CREDENCIAL:
            raise CredencialesInvalidasError(
                "Usuario o contraseña incorrectos en el campus."
            )
        if codigo in _ERRORES_DE_SERVICIO:
            raise ServicioNoHabilitadoError(
                "Tu usuario y contraseña son correctos, pero el campus no te permite "
                "generar una llave de acceso. Pedile al administrador del campus que "
                "te habilite para el servicio de ActiveExam."
            )
        raise TokenExchangeError(f"El campus rechazó el pedido ({codigo or 'sin código'}).")

    token = body.get("token")
    if not token or not isinstance(token, str):
        raise TokenExchangeError("El campus no devolvió un token.")

    return TokenObtenido(
        token=token,
        tiene_private_token=bool(body.get("privatetoken")),
    )
