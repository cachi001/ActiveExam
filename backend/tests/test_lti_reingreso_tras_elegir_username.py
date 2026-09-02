"""El alumno que ya eligió su username tiene que poder volver a entrar por el campus.

Por qué existe
--------------
El diseño es: quien entra por el link de Moodle **elige su propio usuario y su
contraseña** la primera vez (`PUT /auth/change-password` con `nuevo_username`, que
el backend EXIGE en el primer set de una cuenta LTI). El `lti:{deployment}:{sub}`
con el que nace la cuenta es un provisorio hasta ese momento.

El problema: el reingreso busca la cuenta existente **por ese username sintético**
(`jit_provisioning.py`, único `select` de la función). Una vez que la persona lo
reemplazó por el suyo, esa búsqueda ya no la encuentra, y el flujo se va por la
rama de "crear cuenta nueva".

Lo que pasa después depende de un accidente: si el email del launch coincide con
el de la cuenta, el INSERT viola el UNIQUE de email y la rama de fusión la
recupera. Si NO coincide — porque la primera vez Moodle no mandó email y la
cuenta quedó con el sintético `@sin-email.lti.local` — no hay colisión y se crea
una SEGUNDA cuenta: la persona entra sin su consentimiento, sin su biometría y
sin su historial, el día del examen.

El identificador estable de la identidad LTI es el `sub` del launch (el userid de
Moodle), no un username que su dueño puede cambiar.

Contra DB REAL, sin mocks (regla dura de código).
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select, text

from app.application.lti.jit_provisioning import provisionar_o_recuperar_usuario
from app.infrastructure.persistence.models.transactional import UsuarioModel
from tests.test_c75_lti_jit import (  # noqa: F401 -- fixtures reutilizadas
    _DEPLOYMENT_ID,
    _ISS,
    _insertar_deployment,
    _limpiar_db,
    db_url,
    engine,
    session_factory,
)

CLAIM_DEPLOYMENT_ID = "https://purl.imsglobal.org/spec/lti/claim/deployment_id"


def _claims_de(sub: str, email: str | None) -> dict:
    claims = {
        "sub": sub,
        "iss": _ISS,
        "name": "Alumno Que Eligió Su Usuario",
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
    }
    if email is not None:
        claims["email"] = email
    return claims


async def _elegir_username(session_factory, *, usuario_id: str, nuevo: str) -> None:
    """Hace lo mismo que el primer set de credenciales: reemplaza el username."""
    async with session_factory() as s:
        await s.execute(
            text(
                "UPDATE usuario SET username = :nuevo, debe_cambiar_password = false"
                " WHERE id = :id"
            ),
            {"nuevo": nuevo, "id": usuario_id},
        )
        await s.commit()


async def _limpiar_lti(session_factory) -> None:
    """Limpieza propia de este módulo.

    `_limpiar_db` borra por `username LIKE 'lti:%'`, y estos tests justamente
    RENOMBRAN el username: la fila sobrevivía entre corridas y contaminaba la
    siguiente (el primer launch se fusionaba con el sobrante por email y el test
    fallaba por una razón que no era la que se estaba probando).
    """
    await _limpiar_db(session_factory)
    async with session_factory() as s:
        await s.execute(text("DELETE FROM inscripcion"))
        await s.execute(text("DELETE FROM usuario WHERE auth_provider = 'lti'"))
        await s.commit()


async def _cuentas_lti(session_factory) -> int:
    async with session_factory() as s:
        return (
            await s.execute(
                select(func.count()).select_from(UsuarioModel).where(
                    UsuarioModel.auth_provider == "lti"
                )
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_reingreso_encuentra_la_cuenta_aunque_haya_cambiado_el_username(
    session_factory,
):
    """El caso normal del sábado: entró, eligió su usuario, y vuelve a entrar."""
    await _limpiar_lti(session_factory)
    dep = await _insertar_deployment(session_factory)
    claims = _claims_de("mdl-7", "alumno7@uni.edu")

    async with session_factory() as s:
        u1, creado1 = await provisionar_o_recuperar_usuario(s, claims=claims, deployment=dep)
        await s.commit()
        uid = u1.id
    assert creado1 is True

    await _elegir_username(session_factory, usuario_id=uid, nuevo="juanperez")

    async with session_factory() as s:
        u2, creado2 = await provisionar_o_recuperar_usuario(s, claims=claims, deployment=dep)
        await s.commit()

    assert creado2 is False, "el reingreso creó una cuenta nueva en vez de encontrar la suya"
    assert u2.id == uid, "el reingreso devolvió OTRA cuenta"
    assert await _cuentas_lti(session_factory) == 1


@pytest.mark.asyncio
async def test_reingreso_sin_email_la_primera_vez_no_duplica_la_cuenta(
    session_factory,
):
    """El caso que rompe de verdad.

    Si en el primer launch Moodle no mandó email, la cuenta queda con el sintético
    `@sin-email.lti.local`. Cuando el segundo launch SÍ trae email, no hay
    colisión que rescate nada: se crea una segunda cuenta y la persona pierde su
    consentimiento, su biometría y su historial.
    """
    await _limpiar_lti(session_factory)
    dep = await _insertar_deployment(session_factory)

    async with session_factory() as s:
        u1, _ = await provisionar_o_recuperar_usuario(
            s, claims=_claims_de("mdl-8", None), deployment=dep
        )
        await s.commit()
        uid = u1.id

    await _elegir_username(session_factory, usuario_id=uid, nuevo="mariagomez")

    async with session_factory() as s:
        u2, creado2 = await provisionar_o_recuperar_usuario(
            s, claims=_claims_de("mdl-8", "maria@uni.edu"), deployment=dep
        )
        await s.commit()

    assert creado2 is False, "se creó una cuenta NUEVA para alguien que ya existía"
    assert u2.id == uid
    assert await _cuentas_lti(session_factory) == 1, "quedaron dos cuentas del mismo alumno"


@pytest.mark.asyncio
async def test_dos_alumnos_distintos_que_comparten_email_no_terminan_en_la_misma_cuenta(
    session_factory,
):
    """La otra cara de reconocer a la gente por el mail.

    Dos alumnos REALES distintos (dos `sub` distintos de Moodle) que compartan
    dirección de correo. Si la identidad se decide por el mail, el segundo entra
    a la cuenta del primero: rinde con su historial, su consentimiento y su
    biometría. Es peor que crear una cuenta de más.
    """
    await _limpiar_lti(session_factory)
    dep = await _insertar_deployment(session_factory)
    compartido = "catedra.compartida@uni.edu"

    async with session_factory() as s:
        primero, _ = await provisionar_o_recuperar_usuario(
            s, claims=_claims_de("mdl-100", compartido), deployment=dep
        )
        await s.commit()
        id_primero = primero.id

    # Se BLOQUEA el launch, y es a propósito: el correo es UNIQUE, así que las dos
    # cuentas no pueden coexistir con esa dirección, y entregarle al segundo la
    # cuenta del primero es peor que no dejarlo entrar. Un launch que falla con un
    # motivo claro se arregla corrigiendo el dato en el campus.
    from app.application.lti.jit_provisioning import LaunchInvalidoError

    with pytest.raises(LaunchInvalidoError) as caso:
        async with session_factory() as s:
            segundo, _ = await provisionar_o_recuperar_usuario(
                s, claims=_claims_de("mdl-200", compartido), deployment=dep
            )
            await s.commit()
            assert segundo.id != id_primero, (
                "el alumno mdl-200 entró a la cuenta de mdl-100: son dos personas distintas"
            )

    assert "email_compartido" in str(caso.value)


# ---------------------------------------------------------------------------
# La identidad de Moodle en su propia columna (migración 0106)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_al_crear_la_cuenta_se_guarda_el_userid_de_moodle(session_factory):
    """El `sub` del launch ES el userid de Moodle: se guarda como tal."""
    await _limpiar_lti(session_factory)
    dep = await _insertar_deployment(session_factory)

    async with session_factory() as s:
        u, _ = await provisionar_o_recuperar_usuario(
            s, claims=_claims_de("77", "setenta.siete@uni.edu"), deployment=dep
        )
        await s.commit()

    assert u.moodle_userid == "77"
    assert u.lti_deployment_id == _DEPLOYMENT_ID


@pytest.mark.asyncio
async def test_el_reingreso_lo_encuentra_aunque_cambien_username_Y_email(
    session_factory,
):
    """La prueba de fuego: se le cambian las DOS cosas por las que se lo buscaba.

    Si lo encuentra igual, la identidad dejó de depender de datos prestados.
    """
    await _limpiar_lti(session_factory)
    dep = await _insertar_deployment(session_factory)

    async with session_factory() as s:
        u1, _ = await provisionar_o_recuperar_usuario(
            s, claims=_claims_de("mdl-9", "viejo@uni.edu"), deployment=dep
        )
        await s.commit()
        uid = u1.id

    await _elegir_username(session_factory, usuario_id=uid, nuevo="pedro_gomez")
    # El correo de la cuenta cambia y el del launch NO: es lo que pasa cuando la
    # persona (o un admin) actualiza su dirección de este lado. Si los dos
    # cambiaran igual, el test volvería a probar el rescate por correo en vez de
    # la identidad de Moodle.
    async with session_factory() as s:
        await s.execute(
            text("UPDATE usuario SET email = 'cambiado@uni.edu' WHERE id = :id"),
            {"id": uid},
        )
        await s.commit()

    async with session_factory() as s:
        u2, creado = await provisionar_o_recuperar_usuario(
            s, claims=_claims_de("mdl-9", "viejo@uni.edu"), deployment=dep
        )
        await s.commit()

    assert creado is False
    assert u2.id == uid
    assert await _cuentas_lti(session_factory) == 1


@pytest.mark.asyncio
async def test_una_cuenta_vieja_sin_el_dato_se_completa_sola_al_entrar(
    session_factory,
):
    """Autorrelleno: las cuentas anteriores no quedan rotas para siempre.

    Se simula una cuenta previa a la migración (sin `moodle_userid`) que además ya
    había cambiado su username. Al entrar por el campus, se la reconoce por el
    camino viejo (el correo) y se le graba la identidad de Moodle: la próxima vez
    ya entra por el camino bueno.
    """
    await _limpiar_lti(session_factory)
    dep = await _insertar_deployment(session_factory)

    async with session_factory() as s:
        u1, _ = await provisionar_o_recuperar_usuario(
            s, claims=_claims_de("mdl-10", "vieja@uni.edu"), deployment=dep
        )
        await s.commit()
        uid = u1.id

    await _elegir_username(session_factory, usuario_id=uid, nuevo="cuenta_vieja")
    async with session_factory() as s:
        await s.execute(
            text(
                "UPDATE usuario SET moodle_userid = NULL, lti_deployment_id = NULL,"
                " attrs_federados = '{}'::jsonb WHERE id = :id"
            ),
            {"id": uid},
        )
        await s.commit()

    async with session_factory() as s:
        u2, creado = await provisionar_o_recuperar_usuario(
            s, claims=_claims_de("mdl-10", "vieja@uni.edu"), deployment=dep
        )
        await s.commit()

    assert creado is False
    assert u2.id == uid
    assert u2.moodle_userid == "mdl-10", "no se completó la identidad al entrar"


@pytest.mark.asyncio
async def test_no_se_le_entrega_a_un_launch_la_cuenta_de_un_docente(session_factory):
    """Guarda que ya existía y NO se puede perder al tocar esta cadena.

    Si el correo del launch pertenece a una cuenta que no es LTI (un docente, un
    admin), el launch se rechaza. Entregarla sería darle a cualquiera que sepa un
    correo el rol y el acceso de esa persona.
    """
    from app.application.lti.jit_provisioning import LaunchInvalidoError

    import uuid as _uuid

    await _limpiar_lti(session_factory)
    dep = await _insertar_deployment(session_factory)
    # Únicos por corrida: es una cuenta LOCAL, y `_limpiar_lti` solo borra las LTI.
    sufijo = _uuid.uuid4().hex[:8]
    correo_docente = f"profe-{sufijo}@uni.edu"

    async with session_factory() as s:
        await s.execute(
            text(
                "INSERT INTO usuario (username, email, roles, auth_provider,"
                " password_hash, attrs_federados)"
                " VALUES (:u, :e, '[\"tutor\"]'::jsonb, 'local', 'x', '{}'::jsonb)"
            ),
            {"u": f"profe_ajeno_{sufijo}", "e": correo_docente},
        )
        await s.commit()

    with pytest.raises(LaunchInvalidoError):
        async with session_factory() as s:
            await provisionar_o_recuperar_usuario(
                s, claims=_claims_de("mdl-11", correo_docente), deployment=dep
            )
            await s.commit()
