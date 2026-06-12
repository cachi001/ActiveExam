"""Servicio DSR — orquesta los 4 derechos del titular (c-17 slim).

Reutiliza el ``HoldVerifier`` del dominio retention (c-19) para diferir
borrados de sesiones con caso disciplinario abierto. En slim el verifier
default es Null (no hay tabla `caso_disciplinario`) — c-69 lo reemplaza.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.dsr.ports import DsrAuditor, UserDsrRepository
from app.domain.dsr.report import (
    DsrAccessResponse,
    DsrErasureReport,
    DsrPortabilityResponse,
    DsrType,
)
from app.domain.retention.hold import HoldDecision, HoldVerifier


_PURPOSE_BY_TYPE = {
    DsrType.ACCESS: "DSR: acceso a datos personales (Ley 25.326)",
    DsrType.RECTIFICATION: "DSR: rectificacion de datos personales (Ley 25.326)",
    DsrType.ERASURE: "DSR: eliminacion / derecho al olvido (Ley 25.326)",
    DsrType.PORTABILITY: "DSR: portabilidad en formato exportable (Ley 25.326)",
}


def _to_access_response(u: dict) -> DsrAccessResponse:
    return DsrAccessResponse(
        usuario_id=str(u["id"]),
        id_institucional=u["id_institucional"],
        email=u["email"],
        nombre=u.get("nombre"),
        apellido=u.get("apellido"),
        roles=list(u.get("roles") or []),
        eliminado_en=(
            u["eliminado_en"].isoformat()
            if u.get("eliminado_en") and hasattr(u["eliminado_en"], "isoformat")
            else (u.get("eliminado_en") or None)
        ),
    )


@dataclass
class DsrService:
    """Implementa los 4 derechos del titular sobre slim."""

    repo: UserDsrRepository
    hold_verifier: HoldVerifier
    auditor: DsrAuditor

    async def access(
        self, usuario_id: str, *, actor: str
    ) -> DsrAccessResponse:
        u = await self.repo.get_user(usuario_id)
        if u is None:
            raise ValueError(f"Usuario {usuario_id!r} no encontrado")
        await self.auditor.log_dsr(
            usuario_id,
            actor=actor,
            tipo=DsrType.ACCESS.value,
            proposito=_PURPOSE_BY_TYPE[DsrType.ACCESS],
        )
        return _to_access_response(u)

    async def rectification(
        self,
        usuario_id: str,
        *,
        actor: str,
        email: str | None,
        nombre: str | None,
        apellido: str | None,
    ) -> DsrAccessResponse:
        u = await self.repo.get_user(usuario_id)
        if u is None:
            raise ValueError(f"Usuario {usuario_id!r} no encontrado")
        await self.repo.update_user_fields(
            usuario_id, email=email, nombre=nombre, apellido=apellido
        )
        await self.auditor.log_dsr(
            usuario_id,
            actor=actor,
            tipo=DsrType.RECTIFICATION.value,
            proposito=_PURPOSE_BY_TYPE[DsrType.RECTIFICATION],
        )
        # Re-leer con los campos ya actualizados
        u_after = await self.repo.get_user(usuario_id)
        if u_after is None:
            raise ValueError(f"Usuario {usuario_id!r} desaparecio tras update")
        return _to_access_response(u_after)

    async def portability(
        self, usuario_id: str, *, actor: str
    ) -> DsrPortabilityResponse:
        u = await self.repo.get_user(usuario_id)
        if u is None:
            raise ValueError(f"Usuario {usuario_id!r} no encontrado")
        sessions = await self.repo.list_sessions_for_user(usuario_id)
        await self.auditor.log_dsr(
            usuario_id,
            actor=actor,
            tipo=DsrType.PORTABILITY.value,
            proposito=_PURPOSE_BY_TYPE[DsrType.PORTABILITY],
        )
        return DsrPortabilityResponse(
            usuario_id=str(u["id"]),
            id_institucional=u["id_institucional"],
            email=u["email"],
            nombre=u.get("nombre"),
            apellido=u.get("apellido"),
            roles=list(u.get("roles") or []),
            session_ids=sessions,
        )

    async def erasure(
        self, usuario_id: str, *, actor: str
    ) -> DsrErasureReport:
        """Borra biometria + sesiones sin hold + anonimiza si no quedan holds.

        Importante (Ley 25.326):
        - Biometria (embedding + foto) se borra SIEMPRE — no depende de holds
          de sesiones, es por minimizacion del dato sensible al egreso.
        - Sesiones con hold se DIFIEREN — vuelven al regimen normal cuando
          el hold se libera (c-69 manejara la coordinacion).
        - Anonimizacion del usuario ocurre SOLO si no quedan sesiones con hold
          (el titular queda preservado como "involucrado en proceso abierto").
        """
        u = await self.repo.get_user(usuario_id)
        if u is None:
            raise ValueError(f"Usuario {usuario_id!r} no encontrado")

        # Biometria siempre
        embeddings = await self.repo.delete_embeddings(usuario_id)
        fotos = await self.repo.delete_fotos(usuario_id)

        # Sesiones: respetando holds
        sessions = await self.repo.list_sessions_for_user(usuario_id)
        deleted: list[str] = []
        deferred: list[str] = []
        for sid in sessions:
            decision = await self.hold_verifier.verify(sid)
            if decision == HoldDecision.HOLD:
                deferred.append(sid)
            else:
                await self.repo.delete_session(sid)
                deleted.append(sid)

        # Anonimizacion: solo si no quedan holds que preservar
        anonimizado = False
        if not deferred:
            await self.repo.anonymize_user(usuario_id)
            anonimizado = True

        await self.auditor.log_dsr(
            usuario_id,
            actor=actor,
            tipo=DsrType.ERASURE.value,
            proposito=_PURPOSE_BY_TYPE[DsrType.ERASURE],
        )

        return DsrErasureReport(
            usuario_id=str(u["id"]),
            embeddings_deleted=embeddings,
            fotos_deleted=fotos,
            sessions_deleted=deleted,
            sessions_deferred=deferred,
            anonimizado=anonimizado,
        )
