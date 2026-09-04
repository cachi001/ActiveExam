"""La sesión de examen referencia al alumno por su id, no por un texto.

Por qué existe
--------------
`proctoring_session` no guardaba el id del usuario. Guardaba dos textos —
`alumno_idnumber` (el username) y `alumno_email` — y con el username hacía de
llave para joinear contra `usuario`: así se resuelve el nombre que ve el tutor en
supervisión en vivo y así se llega al `moodle_userid` para devolver la nota.

Lo absurdo es que el id ESTABA a mano en el momento de crear la sesión: es
`principal.subject`, que dos líneas más arriba se usa para chequear el perfil del
alumno. Se tenía la clave primaria y se persistía un texto mutable en su lugar.

Por qué importa, y no es teoría: el username lo elige la persona en su primer
ingreso por el campus. Una sesión creada antes de ese momento queda apuntando a
un username que ya no existe, y el join no la encuentra: el tutor deja de ver de
quién es la sesión, y la nota pierde el camino a Moodle.

`alumno_idnumber` no se toca ni se renombra: deja de ser una llave y queda siendo
lo único que tiene sentido que sea, la foto del username que la persona tenía en
ese momento, que como evidencia de una rendición sirve.

Contra DB REAL, sin mocks (regla dura de código).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.proctoring.conftest import ALUMNO_DE_TEST, auth_headers

pytestmark = pytest.mark.asyncio

_ADMIN = auth_headers(["admin_sistema"])


async def _crear_usuario(db, *, username: str, nombre: str, apellido: str) -> str:
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


async def _crear_sesion(client: AsyncClient, *, usuario_id: str, username: str) -> str:
    """Crea la sesión como la crea el alumno, con SU token."""
    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "examen", "etiqueta": "Parcial 1"},
        headers=auth_headers(
            ["estudiante"],
            username=username,
            email=f"{username}@uni.edu",
            subject=usuario_id,
        ),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_la_sesion_guarda_el_id_del_alumno(client, db_session):
    """El id estaba disponible al crearla y no se persistía."""
    username = f"lise-{uuid.uuid4().hex[:8]}"
    uid = await _crear_usuario(db_session, username=username, nombre="Lise", apellido="Meitner")
    sid = await _crear_sesion(client, usuario_id=uid, username=username)

    fila = (
        await db_session.execute(
            text("SELECT alumno_usuario_id FROM proctoring_session WHERE id = :id"),
            {"id": sid},
        )
    ).scalar_one()

    assert str(fila) == uid


async def test_el_tutor_sigue_viendo_a_la_persona_si_cambian_sus_datos(
    client, db_session
):
    """El caso que rompe: la sesión apunta a datos que ya no existen.

    Con el username SOLO no alcanzaba para romperlo: el resolver del nombre
    matchea por username OR email, así que el correo lo rescataba. Se cambian los
    dos, que es cuando el join se queda sin nada — y es lo que pasa cuando alguien
    elige su usuario en el primer ingreso y además actualiza su dirección.
    """
    username = f"emmy-{uuid.uuid4().hex[:8]}"
    uid = await _crear_usuario(db_session, username=username, nombre="Emmy", apellido="Noether")
    sid = await _crear_sesion(client, usuario_id=uid, username=username)

    await db_session.execute(
        text("UPDATE usuario SET username = :nuevo, email = :mail WHERE id = :id"),
        {
            "nuevo": f"otro-{uuid.uuid4().hex[:8]}",
            "mail": f"otro-{uuid.uuid4().hex[:8]}@uni.edu",
            "id": uid,
        },
    )
    await db_session.commit()

    resp = await client.get("/api/v1/proctoring/sessions", headers=_ADMIN)
    assert resp.status_code == 200, resp.text
    fila = next((s for s in resp.json() if s["id"] == sid), None)
    assert fila is not None

    assert fila["alumno_nombre"] == "Emmy Noether", (
        "al cambiar el username, el tutor dejó de ver de quién es la sesión"
    )


async def test_las_sesiones_viejas_sin_id_se_siguen_resolviendo(client, db_session):
    """Triangulación: las que ya existen no tienen el id y no pueden quedar rotas.

    Se las sigue resolviendo por el camino de siempre (el username).
    """
    username = f"rosalind-{uuid.uuid4().hex[:8]}"
    uid = await _crear_usuario(
        db_session, username=username, nombre="Rosalind", apellido="Franklin"
    )
    sid = await _crear_sesion(client, usuario_id=uid, username=username)

    # Simula una sesión anterior a la migración: sin el id.
    await db_session.execute(
        text("UPDATE proctoring_session SET alumno_usuario_id = NULL WHERE id = :id"),
        {"id": sid},
    )
    await db_session.commit()

    resp = await client.get("/api/v1/proctoring/sessions", headers=_ADMIN)
    fila = next((s for s in resp.json() if s["id"] == sid), None)
    assert fila is not None
    assert fila["alumno_nombre"] == "Rosalind Franklin"
