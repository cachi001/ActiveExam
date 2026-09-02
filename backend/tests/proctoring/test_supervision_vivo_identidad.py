"""Supervisión en vivo dice DE QUIÉN es cada sesión.

Por qué existe
--------------
Encontrado el 2/9/2026 recorriendo `/proctor` como tutor, con el examen real del
5/9 a tres días. El panel mostraba, en la tarjeta de cada persona, **el título
del examen en vez del nombre del alumno**.

La cadena era esta:

1. el repositorio SÍ resuelve la identidad server-side (``_armar_resumenes``
   trae ``alumno_nombre``/``alumno_idnumber``/``alumno_email`` en lote contra
   ``usuario``)
2. el router de supervisión en vivo los DESCARTABA al construir la respuesta:
   el schema los declaraba, nadie los pasaba, salían siempre ``null``
3. sin eso, la pantalla caía a ``etiqueta``, que **la manda el cliente**

Las dos consecuencias, y por eso esto es un test y no un detalle de UI:

- con 40 alumnos rindiendo, si el nombre no estaba cargado en el cliente al
  crear la sesión, el tutor veía 40 tarjetas que decían todas lo mismo
- el cliente es un sensor no confiable (regla dura #6): la etiqueta puede decir
  cualquier cosa, incluso el nombre de OTRA persona

Contra DB REAL, sin mocks (regla dura de código).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.proctoring.conftest import auth_headers

pytestmark = pytest.mark.asyncio

_ADMIN = auth_headers(["admin_sistema"])


async def _crear_usuario(db, *, username: str, nombre: str, apellido: str) -> str:
    """Siembra un usuario real: es contra esta tabla que se resuelve la identidad."""
    from app.infrastructure.persistence.base import Base
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    await db.run_sync(
        lambda sync: Base.metadata.create_all(
            sync.get_bind(), tables=[UsuarioModel.__table__], checkfirst=True
        )
    )
    uid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO usuario (id, username, email, nombre, apellido,"
            " password_hash, roles)"
            " VALUES (:id, :u, :e, :n, :a, 'x', '[\"estudiante\"]'::jsonb)"
        ),
        {"id": uid, "u": username, "e": f"{username}@uni.edu", "n": nombre, "a": apellido},
    )
    await db.commit()
    return uid


async def _sesion_de(client: AsyncClient, *, username: str, etiqueta: str) -> str:
    """Crea la sesión como la crea el alumno: la etiqueta la elige el cliente."""
    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "examen", "etiqueta": etiqueta},
        headers=auth_headers(
            ["estudiante"], username=username, email=f"{username}@uni.edu"
        ),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _resumen(client: AsyncClient, session_id: str) -> dict:
    resp = await client.get("/api/v1/proctoring/sessions", headers=_ADMIN)
    assert resp.status_code == 200, resp.text
    fila = next((s for s in resp.json() if s["id"] == session_id), None)
    assert fila is not None, "la sesión recién creada no aparece en el panel en vivo"
    return fila


async def test_el_panel_en_vivo_trae_el_nombre_del_alumno(client, db_session):
    """Sin esto el tutor no sabe a quién está mirando."""
    username = f"ada-{uuid.uuid4().hex[:8]}"
    await _crear_usuario(db_session, username=username, nombre="Ada", apellido="Lovelace")
    sid = await _sesion_de(client, username=username, etiqueta="Parcial 1")

    fila = await _resumen(client, sid)

    assert fila["alumno_nombre"] == "Ada Lovelace"
    assert fila["alumno_idnumber"] == username


async def test_la_identidad_sale_del_servidor_aunque_la_etiqueta_diga_otra_cosa(
    client, db_session
):
    """Regla dura #6: el cliente es un sensor no confiable.

    La etiqueta la elige quien crea la sesión. Si la pantalla se guiara por ella,
    alguien podría hacerse pasar por otro en el panel del tutor.
    """
    username = f"grace-{uuid.uuid4().hex[:8]}"
    await _crear_usuario(db_session, username=username, nombre="Grace", apellido="Hopper")
    sid = await _sesion_de(client, username=username, etiqueta="Ada Lovelace")

    fila = await _resumen(client, sid)

    assert fila["alumno_nombre"] == "Grace Hopper", (
        "la identidad tiene que salir de la base, no de lo que mandó el cliente"
    )
    # La etiqueta se sigue devolviendo (es el fallback de la pantalla), pero ya no
    # es la fuente de la identidad.
    assert fila["etiqueta"] == "Ada Lovelace"


async def test_un_alumno_que_no_esta_en_la_base_no_inventa_nombre(client, db_session):
    """Triangulación: sin fila en `usuario` no hay nombre que resolver.

    Devolver null es correcto: la pantalla cae a la etiqueta y avisa que no pudo
    identificarlo, en vez de mostrar un nombre inventado.
    """
    sid = await _sesion_de(
        client, username=f"fantasma-{uuid.uuid4().hex[:8]}", etiqueta="Sin registro"
    )

    fila = await _resumen(client, sid)

    assert fila["alumno_nombre"] is None
