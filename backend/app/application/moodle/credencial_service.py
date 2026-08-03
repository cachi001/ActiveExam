"""Resolucion de la credencial de servicio de Moodle (DB cifrada > entorno).

La credencial (base_url + token de Web Services + tipo de actividad por defecto)
dejo de vivir solo en variables de entorno: ahora la administra el admin del sistema y se guarda
en `moodle_credencial` con el token CIFRADO (migracion 0047).

PRECEDENCIA: si hay fila en la base CON token, manda la base. Si no, se cae a las
variables de entorno (MOODLE_*). Asi un despliegue existente sigue funcionando sin
tocar nada, y el dia que el admin carga el token desde la UI, la base pasa a mandar
sin necesidad de un deploy.

El token NUNCA sale de aca en claro salvo hacia el cliente HTTP de Moodle: no se
loguea, no se audita y no se devuelve por la API.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.crypto.secret_encryption import SecretCipher
from app.infrastructure.persistence.models.transactional import MoodleCredencialModel


@dataclass(frozen=True, slots=True)
class CredencialMoodle:
    """Credencial efectiva ya resuelta (token EN CLARO — no serializar)."""

    base_url: str
    ws_token: str
    component: str
    #: De donde salio: "db" | "env" | "sin_configurar". Para diagnostico y UI.
    origen: str

    @property
    def configurada(self) -> bool:
        """True si alcanza para escribir notas (hay URL y token)."""
        return bool(self.base_url and self.ws_token)


@dataclass(frozen=True, slots=True)
class EstadoCredencial:
    """Vista SEGURA de la credencial para la API (sin el token)."""

    base_url: str
    component: str
    token_configurado: bool
    token_pista: str | None
    origen: str
    actualizado_en: str | None
    actualizado_por: str | None
    #: Shortname del servicio externo del campus (C-73 §10). No es secreto.
    service_shortname: str = ""


class MoodleCredencialResolver:
    """Resuelve la credencial efectiva, con cache invalidable.

    Cachea porque la resuelve el cliente HTTP en CADA llamada a Moodle; sin cache,
    sincronizar 300 notas serian 300 SELECT + 300 descifrados. El cache se invalida
    explicitamente cuando el admin guarda una credencial nueva.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        cipher: SecretCipher,
        env_base_url: str = "",
        env_token: str = "",
        env_component: str = "mod_assign",
    ) -> None:
        self._factory = session_factory
        self._cipher = cipher
        self._env = CredencialMoodle(
            base_url=env_base_url,
            ws_token=env_token,
            component=env_component,
            origen="env" if env_base_url and env_token else "sin_configurar",
        )
        self._cache: CredencialMoodle | None = None

    def invalidate(self) -> None:
        """Invalida el cache: la proxima resolucion vuelve a leer la base."""
        self._cache = None

    async def resolver(self) -> CredencialMoodle:
        """Credencial efectiva. Base (si tiene token) > entorno."""
        if self._cache is not None:
            return self._cache
        fila = await self._leer_fila()
        resuelta = self._env
        if fila is not None and fila.token_cifrado:
            token = self._cipher.decrypt(fila.token_cifrado)
            if token:
                resuelta = CredencialMoodle(
                    base_url=fila.base_url or self._env.base_url,
                    ws_token=token,
                    component=fila.component or "mod_assign",
                    origen="db",
                )
        self._cache = resuelta
        return resuelta

    async def estado(self) -> EstadoCredencial:
        """Vista para la API: dice SI hay token, nunca cual."""
        fila = await self._leer_fila()
        if fila is not None and fila.token_cifrado:
            return EstadoCredencial(
                base_url=fila.base_url,
                component=fila.component,
                token_configurado=True,
                token_pista=fila.token_pista,
                origen="db",
                actualizado_en=str(fila.actualizado_en) if fila.actualizado_en else None,
                actualizado_por=fila.actualizado_por,
                service_shortname=fila.service_shortname or "",
            )
        # Sin fila util: lo que rige es el entorno (o nada).
        return EstadoCredencial(
            base_url=fila.base_url if fila is not None and fila.base_url else self._env.base_url,
            component=fila.component if fila is not None else self._env.component,
            token_configurado=bool(self._env.ws_token),
            token_pista=None,
            origen=self._env.origen,
            actualizado_en=None,
            actualizado_por=None,
            # OJO: `service_shortname` vive en la fila AUNQUE no haya token
            # institucional cargado. Son cosas independientes: el token es la
            # credencial de servicio (respaldo, solo para anulaciones) y el shortname
            # es lo que necesitan los DOCENTES para conectar su propia cuenta. Si no
            # se devolviera acá, el admin lo cargaba, la pantalla lo mostraba vacío y
            # parecía que no se guardó.
            service_shortname=(fila.service_shortname or "") if fila is not None else "",
        )

    async def guardar(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        component: str | None = None,
        service_shortname: str | None = None,
        actor: str | None = None,
    ) -> EstadoCredencial:
        """Upsert de la credencial. ``token=None`` NO borra el token existente.

        Para no obligar al admin a re-tipear el token cada vez que corrige la URL:
        solo se reescribe si viene uno nuevo. Se guarda cifrado.
        """
        from app.infrastructure.crypto.secret_encryption import pista_de_secreto

        async with self._factory() as session:
            fila = await self._obtener_o_crear(session)
            if base_url is not None:
                fila.base_url = base_url.rstrip("/")
            if component is not None:
                fila.component = component
            if service_shortname is not None:
                # C-73 §10: sin esto ningun docente puede canjear su contrasena por un
                # token; `login/token.php` exige `service=`.
                fila.service_shortname = service_shortname.strip()
            if token:
                fila.token_cifrado = self._cipher.encrypt(token)
                fila.token_pista = pista_de_secreto(token)
            fila.actualizado_por = actor
            await session.commit()
        self.invalidate()
        return await self.estado()

    async def borrar_token(self, *, actor: str | None = None) -> EstadoCredencial:
        """Elimina el token guardado (deja de escribir notas hasta cargar otro)."""
        async with self._factory() as session:
            fila = await self._obtener_o_crear(session)
            fila.token_cifrado = None
            fila.token_pista = None
            fila.actualizado_por = actor
            await session.commit()
        self.invalidate()
        return await self.estado()

    # --- internos ---------------------------------------------------------

    async def _leer_fila(self) -> MoodleCredencialModel | None:
        async with self._factory() as session:
            result = await session.execute(
                select(MoodleCredencialModel).where(MoodleCredencialModel.id == 1)
            )
            return result.scalar_one_or_none()

    async def _obtener_o_crear(self, session: AsyncSession) -> MoodleCredencialModel:
        result = await session.execute(
            select(MoodleCredencialModel).where(MoodleCredencialModel.id == 1)
        )
        fila = result.scalar_one_or_none()
        if fila is None:
            fila = MoodleCredencialModel(id=1, base_url="")
            session.add(fila)
            await session.flush()
        return fila
