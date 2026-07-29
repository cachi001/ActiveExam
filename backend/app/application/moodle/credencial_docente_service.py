"""Credencial personal de Moodle de cada docente (C-73 §10).

Con esta credencial se devuelven las notas de las comisiones que el docente tiene a
cargo, para que en la libreta la nota figure puesta POR EL y para que sea Moodle
—no nuestro codigo— quien impida escribir donde no da clase.

LA CONTRASENA NO SE GUARDA. Se usa una vez para canjearla por un token
(`token_exchange`) y se descarta. El token se persiste cifrado con `SecretCipher`.
La tabla ni siquiera tiene columna para la contrasena.

DOS FORMAS DE CARGARLA, porque no todos los campus habilitan lo mismo:
- Con usuario+contrasena: nosotros canjeamos. Requiere que el campus le permita al
  rol docente emitir su token (`moodle/webservice:createtoken`).
- Pegando un token ya emitido: para campus donde esa capacidad no se otorga y el
  admin genera los tokens a mano. Ventaja: el docente nunca nos escribe su clave.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.moodle.token_exchange import canjear_password_por_token
from app.infrastructure.crypto.secret_encryption import SecretCipher, pista_de_secreto
from app.infrastructure.persistence.models.transactional import (
    MoodleCredencialDocenteModel,
)

ESTADO_ACTIVA = "activa"
ESTADO_CAIDA = "caida"


@dataclass(frozen=True, slots=True)
class EstadoCredencialDocente:
    """Vista SEGURA para la API: nunca incluye el token."""

    configurada: bool
    moodle_username: str | None
    token_pista: str | None
    estado: str | None
    actualizado_en: str | None
    ultimo_uso_en: str | None


_SIN_CREDENCIAL = EstadoCredencialDocente(
    configurada=False,
    moodle_username=None,
    token_pista=None,
    estado=None,
    actualizado_en=None,
    ultimo_uso_en=None,
)


def _iso(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor else None


class CredencialDocenteService:
    """CRUD de la credencial personal + canje. No cachea a proposito.

    A diferencia del resolver institucional, esto se lee una vez por sincronizacion
    (no una vez por nota): cachearlo agregaria invalidacion sin ahorrar nada real, y
    un token cacheado que ya fue revocado es peor que una query de mas.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker,
        cipher: SecretCipher,
    ) -> None:
        self._sf = session_factory
        self._cipher = cipher

    # -- lectura -----------------------------------------------------------

    async def estado(self, usuario_id: str) -> EstadoCredencialDocente:
        fila = await self._leer(usuario_id)
        if fila is None:
            return _SIN_CREDENCIAL
        return EstadoCredencialDocente(
            configurada=True,
            moodle_username=fila.moodle_username,
            token_pista=fila.token_pista,
            estado=fila.estado,
            actualizado_en=_iso(fila.actualizado_en),
            ultimo_uso_en=_iso(fila.ultimo_uso_en),
        )

    async def token_de(self, usuario_id: str) -> str | None:
        """Token EN CLARO del docente, o ``None`` si no tiene o esta caida.

        Una credencial `caida` se trata como ausente a proposito: reintentar con un
        token que Moodle ya rechazo solo produce el mismo error N veces. Quien llama
        cae al respaldo institucional."""
        fila = await self._leer(usuario_id)
        if fila is None or fila.estado != ESTADO_ACTIVA:
            return None
        return self._cipher.decrypt(fila.token_cifrado)

    # -- escritura ---------------------------------------------------------

    async def guardar_con_password(
        self,
        *,
        usuario_id: str,
        moodle_username: str,
        password: str,
        base_url: str,
        service_shortname: str,
    ) -> EstadoCredencialDocente:
        """Canjea la contrasena por un token y guarda SOLO el token.

        La contrasena no se persiste ni se devuelve; si el canje falla, propaga el
        error tipado de `token_exchange` (que tampoco la incluye)."""
        obtenido = await canjear_password_por_token(
            base_url=base_url,
            username=moodle_username,
            password=password,
            service_shortname=service_shortname,
        )
        return await self.guardar_token(
            usuario_id=usuario_id,
            moodle_username=moodle_username,
            token=obtenido.token,
        )

    async def guardar_token(
        self, *, usuario_id: str, moodle_username: str, token: str
    ) -> EstadoCredencialDocente:
        """Persiste un token ya obtenido (canjeado o emitido por el admin del campus)."""
        cifrado = self._cipher.encrypt(token)
        pista = pista_de_secreto(token)
        ahora = datetime.now(timezone.utc)
        async with self._sf() as session:
            fila = await self._leer_en(session, usuario_id)
            if fila is None:
                fila = MoodleCredencialDocenteModel(
                    usuario_id=usuario_id,
                    moodle_username=moodle_username,
                    token_cifrado=cifrado,
                    token_pista=pista,
                    estado=ESTADO_ACTIVA,
                )
                session.add(fila)
            else:
                fila.moodle_username = moodle_username
                fila.token_cifrado = cifrado
                fila.token_pista = pista
                # Recargar una credencial la REACTIVA: es exactamente lo que hace el
                # docente cuando le avisamos que se le cayo.
                fila.estado = ESTADO_ACTIVA
                fila.actualizado_en = ahora
            await session.commit()
        return await self.estado(usuario_id)

    async def marcar_caida(self, usuario_id: str) -> None:
        """Moodle respondio `invalidtoken`: se marca, NO se borra.

        Borrarlo dejaria a la pantalla sin nada que mostrar y el docente no sabria que
        paso. Marcado, se le puede decir 'tu conexion con el campus dejo de funcionar,
        volve a cargarla'."""
        async with self._sf() as session:
            fila = await self._leer_en(session, usuario_id)
            if fila is None:
                return
            fila.estado = ESTADO_CAIDA
            fila.actualizado_en = datetime.now(timezone.utc)
            await session.commit()

    async def marcar_uso(self, usuario_id: str) -> None:
        """Sella el ultimo uso exitoso (diagnostico: 'hace meses que no sincroniza')."""
        async with self._sf() as session:
            fila = await self._leer_en(session, usuario_id)
            if fila is None:
                return
            fila.ultimo_uso_en = datetime.now(timezone.utc)
            await session.commit()

    async def borrar(self, usuario_id: str) -> EstadoCredencialDocente:
        """Desconecta al docente del campus. Idempotente."""
        async with self._sf() as session:
            fila = await self._leer_en(session, usuario_id)
            if fila is not None:
                await session.delete(fila)
                await session.commit()
        return _SIN_CREDENCIAL

    # -- internos ----------------------------------------------------------

    async def _leer(self, usuario_id: str) -> MoodleCredencialDocenteModel | None:
        async with self._sf() as session:
            return await self._leer_en(session, usuario_id)

    async def _leer_en(self, session, usuario_id: str):
        return (
            await session.execute(
                select(MoodleCredencialDocenteModel).where(
                    MoodleCredencialDocenteModel.usuario_id == usuario_id
                )
            )
        ).scalar_one_or_none()
