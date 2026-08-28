"""`sin_token` no salía nunca: la condición miraba lo que no era (27/8/2026).

EL ESTADO: una nota que no se puede enviar porque no hay credencial del campus.
Es distinto de `pendiente` (se puede enviar, todavía no se mandó) y sobre todo de
`fallido` (se intentó y falló). Son tres problemas con tres soluciones distintas.

EL BUG: se mostraba solo si `moodle_configurado` era falso, y eso se calculaba
como `writeback_svc is not None`. Pero `build_writeback_svc_dinamico` construye
el servicio SIEMPRE — su docstring lo dice: "El servicio se construye siempre (no
devuelve None)". Ese cambio fue a propósito, para poder cargar el token desde la
UI sin reiniciar. El efecto colateral es que `moodle_configurado` quedó en true
para siempre y la rama de `sin_token` se volvió inalcanzable.

Consecuencia real: sin credencial, el envío falla y la nota queda `fallido`, que
al docente le dice "Falló el envío" cuando en realidad nunca se intentó. Va a
buscar un problema de red que no existe, en vez de cargar el token.

LA CURA: preguntar por la CREDENCIAL VIGENTE, no por la existencia del objeto.
Con eso `sin_token` vuelve a ser alcanzable, y además se apaga solo en cuanto
alguien carga el token — sin reiniciar y sin tocar las filas ya guardadas.

Por eso `sin_token` NO se persiste: es una condición del sistema en un momento,
no un estado de la nota. Guardarlo dejaría mil filas diciendo "sin token" el día
después de configurar el campus.
"""

from __future__ import annotations

import pytest

from app.application.moodle.resultados_query import (
    ESTADO_MANUAL,
    ESTADO_PENDIENTE,
    ESTADO_SIN_TOKEN,
    estado_moodle_display,
)


def test_sin_credencial_una_nota_pendiente_se_muestra_como_sin_token():
    assert (
        estado_moodle_display(ESTADO_PENDIENTE, moodle_configurado=False)
        == ESTADO_SIN_TOKEN
    )


def test_con_credencial_la_pendiente_sigue_siendo_pendiente():
    assert (
        estado_moodle_display(ESTADO_PENDIENTE, moodle_configurado=True)
        == ESTADO_PENDIENTE
    )


def test_manual_no_se_degrada_a_sin_token():
    # Es justamente el caso en que alguien cargo la nota SIN API. Decirle "sin
    # conexion al campus" a una nota que ya esta cargada seria mentirle.
    assert (
        estado_moodle_display(ESTADO_MANUAL, moodle_configurado=False) == ESTADO_MANUAL
    )


class _ClienteFalso:
    def __init__(self, base_url: str, ws_token: str):
        self._cfg = type("Cfg", (), {"base_url": base_url, "ws_token": ws_token})()

    async def _resolver_config(self):
        return self._cfg


class _ClienteQueLevanta:
    async def _resolver_config(self):
        raise RuntimeError("la base no responde")


@pytest.mark.asyncio
async def test_hay_credencial_true_con_url_y_token():
    from app.application.moodle.writeback_service import MoodleWritebackService

    svc = MoodleWritebackService(moodle_client=_ClienteFalso("https://campus", "tok"))
    assert await svc.hay_credencial() is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("base_url", "token"), [("", "tok"), ("https://campus", ""), ("", "")]
)
async def test_hay_credencial_false_si_falta_alguno(base_url, token):
    # Con uno solo de los dos no se puede llamar a Moodle: falta credencial igual.
    from app.application.moodle.writeback_service import MoodleWritebackService

    svc = MoodleWritebackService(moodle_client=_ClienteFalso(base_url, token))
    assert await svc.hay_credencial() is False


@pytest.mark.asyncio
async def test_si_no_se_puede_resolver_se_asume_sin_credencial():
    # Preferible mostrar "falta conectar el campus" que romper la pantalla de
    # resultados: esta consulta es solo para decidir como MOSTRAR un estado.
    from app.application.moodle.writeback_service import MoodleWritebackService

    svc = MoodleWritebackService(moodle_client=_ClienteQueLevanta())
    assert await svc.hay_credencial() is False
