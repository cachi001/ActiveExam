"""c-78 §16.5 — la captura viaja BINARIA, sin inflarse en base64. Postgres real.

## El problema

La captura sube dentro del JSON como data URL, o sea texto base64: **un tercio más de
bytes** que la imagen. Con 100 alumnos mandando capturas durante dos horas en el plan
free, ese tercio es tiempo de subida que se paga en el enlace del alumno, que puede ser
el wifi de su casa.

## Por qué un endpoint nuevo y no cambiar el que ya existe

El endpoint JSON **se queda igual**. Este es uno nuevo, multipart: los metadatos van en
una parte y los bytes de la imagen en otra, crudos. El servidor reconstruye el data URL
exacto y llama a la MISMA función de ingesta, así que hash, custodia, re-inferencia y
persistencia no cambian.

Eso importa por dos motivos. Uno: `screenshot_sha256` se calcula sobre el string del
data URL y es la base de la cadena de custodia — si el string reconstruido no fuera
idéntico byte a byte, toda la evidencia dejaría de verificar. Dos: a dos semanas del
examen real, un cliente que quede a mitad de camino tiene que poder seguir usando el
endpoint viejo sin que nadie despliegue de urgencia.
"""

from __future__ import annotations

import base64
import hashlib
import os
import uuid

import pytest
from httpx import AsyncClient

from tests.proctoring.conftest import auth_headers

pytestmark = pytest.mark.asyncio

# PNG 1x1 real: que el pipeline lo trate como una imagen de verdad.
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
_PREFIJO = "data:image/png;base64,"
_DATA_URL = _PREFIJO + base64.b64encode(_PNG_1X1).decode()

_RUTA_BIN = "/api/v1/proctoring/sessions/{}/events/binario"
_RUTA_JSON = "/api/v1/proctoring/sessions/{}/events"


async def _crear_sesion(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/proctoring/sessions", json={"modo": "test"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _campos(tipo: str = "FACE_ABSENT", **extra) -> dict:
    base = {
        "tipo": tipo,
        "severidad": "media",
        "ts_cliente": "2026-08-26T20:00:00Z",
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# Lo que NO se puede romper: el hash
# ---------------------------------------------------------------------------


async def test_el_hash_es_identico_al_del_endpoint_json(client: AsyncClient) -> None:
    """`screenshot_sha256` se calcula sobre el string del data URL y sostiene la
    cadena de custodia. La misma imagen por los dos caminos tiene que dar el MISMO
    hash: si no, verify-chain marcaría la evidencia como manipulada."""
    session_id = await _crear_sesion(client)

    por_json = await client.post(
        _RUTA_JSON.format(session_id),
        json=_campos(screenshot_base64=_DATA_URL),
    )
    assert por_json.status_code == 201, por_json.text

    por_binario = await client.post(
        _RUTA_BIN.format(session_id),
        data=_campos(screenshot_prefijo=_PREFIJO),
        files={"captura": ("c.png", _PNG_1X1, "image/png")},
    )
    assert por_binario.status_code == 201, por_binario.text

    assert por_binario.json()["screenshot_sha256"] == por_json.json()["screenshot_sha256"]
    assert (
        por_binario.json()["screenshot_sha256"]
        == hashlib.sha256(_DATA_URL.encode()).hexdigest()
    )


async def test_el_prefijo_da_el_mismo_hash_con_coma_o_sin_ella(
    client: AsyncClient,
) -> None:
    """El prefijo canónico va SIN la coma final. Pero un cliente que parta su data
    URL de la forma obvia la manda incluida, y eso produciría `...base64,,AAAA`: un
    hash distinto, o sea evidencia que no verifica, sin ningún error visible. Las
    dos formas tienen que dar el MISMO hash."""
    session_id = await _crear_sesion(client)

    con_coma = await client.post(
        _RUTA_BIN.format(session_id),
        data=_campos(screenshot_prefijo="data:image/png;base64,"),
        files={"captura": ("c.png", _PNG_1X1, "image/png")},
    )
    sin_coma = await client.post(
        _RUTA_BIN.format(session_id),
        data=_campos(screenshot_prefijo="data:image/png;base64"),
        files={"captura": ("c.png", _PNG_1X1, "image/png")},
    )

    assert con_coma.status_code == 201, con_coma.text
    assert sin_coma.status_code == 201, sin_coma.text
    assert con_coma.json()["screenshot_sha256"] == sin_coma.json()["screenshot_sha256"]
    assert (
        con_coma.json()["screenshot_sha256"]
        == hashlib.sha256(_DATA_URL.encode()).hexdigest()
    )


async def test_el_prefijo_se_guarda_tal_cual_vino(client: AsyncClient) -> None:
    """El prefijo NO se normaliza: se reconstruye el string exacto que mandó el
    cliente. Un `image/jpeg` que volviera como `image/png` cambiaría el hash y
    rompería la custodia de ese evento."""
    session_id = await _crear_sesion(client)
    prefijo_jpeg = "data:image/jpeg;base64,"

    resp = await client.post(
        _RUTA_BIN.format(session_id),
        data=_campos(screenshot_prefijo=prefijo_jpeg),
        files={"captura": ("c.jpg", _PNG_1X1, "image/jpeg")},
    )
    assert resp.status_code == 201, resp.text

    esperado = hashlib.sha256(
        (prefijo_jpeg + base64.b64encode(_PNG_1X1).decode()).encode()
    ).hexdigest()
    assert resp.json()["screenshot_sha256"] == esperado


# ---------------------------------------------------------------------------
# Que la evidencia se pueda recuperar, no solo que el POST responda 201
# ---------------------------------------------------------------------------


async def test_la_captura_guardada_se_lee_igual_que_la_que_entro_por_json(
    client: AsyncClient,
) -> None:
    """Si el revisor abre el detalle y no ve la imagen, el 201 no sirvió de nada.
    Se compara contra el mismo endpoint que usa el revisor."""
    session_id = await _crear_sesion(client)

    resp = await client.post(
        _RUTA_BIN.format(session_id),
        data=_campos("MULTIPLE_FACES", severidad="alta", screenshot_prefijo=_PREFIJO),
        files={"captura": ("c.png", _PNG_1X1, "image/png")},
    )
    assert resp.status_code == 201, resp.text

    detalle = await client.get(
        f"/api/v1/proctoring/sessions/{session_id}",
        headers=auth_headers(["admin_sistema"], subject="revisor-binario"),
    )
    assert detalle.status_code == 200, detalle.text
    eventos = detalle.json()["eventos"]
    assert len(eventos) == 1
    assert eventos[0]["screenshot_base64"] == _DATA_URL


async def test_la_re_inferencia_corre_igual_que_por_el_camino_viejo(
    client: AsyncClient,
) -> None:
    """El servidor no confía en el cliente (regla dura #6): re-infiere sobre la
    imagen recibida. El camino binario no puede saltearse eso."""
    session_id = await _crear_sesion(client)

    resp = await client.post(
        _RUTA_BIN.format(session_id),
        data=_campos(screenshot_prefijo=_PREFIJO, face_count_cliente=1),
        files={"captura": ("c.png", _PNG_1X1, "image/png")},
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["veredicto_reinferencia"] is not None


# ---------------------------------------------------------------------------
# Bordes
# ---------------------------------------------------------------------------


async def test_sin_captura_el_evento_se_registra_igual(client: AsyncClient) -> None:
    """Triangulación: no todos los eventos traen imagen (`cambio_pestana`,
    `copiar_pegar`). El endpoint tiene que aceptarlos sin la parte binaria."""
    session_id = await _crear_sesion(client)

    resp = await client.post(
        _RUTA_BIN.format(session_id),
        data=_campos("cambio_pestana", severidad="baja"),
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["screenshot_sha256"] is None


async def test_una_sesion_ajena_sigue_dando_403(client_noauth: AsyncClient) -> None:
    """El endpoint nuevo no puede ser una puerta de atrás: misma verificación de
    pertenencia que el JSON (H1 del pentest)."""
    resp = await client_noauth.post(
        _RUTA_BIN.format(str(uuid.uuid4())),
        data=_campos(),
        headers=auth_headers(["estudiante"], subject=str(uuid.uuid4())),
    )

    assert resp.status_code in (403, 404), resp.text


async def test_sin_token_no_entra(client_noauth: AsyncClient) -> None:
    resp = await client_noauth.post(
        _RUTA_BIN.format(str(uuid.uuid4())), data=_campos()
    )

    assert resp.status_code == 401, resp.text


def test_el_binario_pesa_menos_que_el_data_url() -> None:
    """El motivo de existir de la tarea, medido: base64 son 4 bytes de texto por
    cada 3 de imagen, y encima el JSON escapa el string."""
    imagen = os.urandom(9000)
    data_url = _PREFIJO + base64.b64encode(imagen).decode()

    assert len(data_url) > len(imagen) * 1.3
