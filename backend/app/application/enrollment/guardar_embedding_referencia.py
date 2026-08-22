"""Application service: GuardarEmbeddingReferenciaService (C-56, task 5.2).

Orquesta:
1. Validar la dimension del embedding (debe ser exactamente 128).
2. Cifrar el embedding con EmbeddingEncryptionService (Fernet).
3. Marcar los embeddings anteriores del usuario como no vigentes.
4. Crear el nuevo registro en embedding_referencia.
5. (C-65, task 7.3) Registrar en audit log si se inyecta audit_repo.

Devuelve el ``referencia_id`` (UUID opaco) para que el cliente lo
persista en el store. El embedding crudo NUNCA sale de este servicio
ni se registra en logs.

D3 del design: el backend acepta el embedding client-side (NO re-infiere
en enrollment). La re-inferencia aplica durante el examen (C-09 D2).

C-65 D6: el audit log se escribe SOLO cuando audit_repo se inyecta
(backward-compatible). Si es None se omite silenciosamente. El origen,
ip y user_agent deben proveerse desde el endpoint para capturar los
valores reales del HTTP request.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.biometrics.embedding_integrity import (
    EmbeddingIntegridadError,
    validar_integridad_embedding,
)
from app.infrastructure.crypto.embedding_encryption import EmbeddingEncryptionService
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.infrastructure.persistence.repositories.biometric_reference import (
    EmbeddingReferenciaRepository,
)

EMBEDDING_DIMENSION = 128

#: Vigencia de la referencia biométrica en meses. Espeja el front
#: (VITE_BIOMETRIC_VALIDITY_MONTHS). Env-configurable, sin hardcode duro.
BIOMETRIC_VALIDITY_MONTHS = int(os.environ.get("BIOMETRIC_VALIDITY_MONTHS", "24"))


class DimensionError(ValueError):
    """El vector no tiene la dimension esperada (128)."""


class RehacerBiometriaBloqueadoError(Exception):
    """El alumno ya tiene una referencia vigente (no vencida) y no hay override
    admin: no puede rehacer la captura hasta que venza o un admin lo habilite."""


def _sumar_meses(dt: datetime, meses: int) -> datetime:
    """Suma ``meses`` calendario a ``dt`` (clamp de día a fin de mes)."""
    total = dt.month - 1 + meses
    anio = dt.year + total // 12
    mes = total % 12 + 1
    # Clamp del día para meses más cortos (ej. 31 ene → 28/29 feb).
    dia = min(dt.day, [31, 29 if anio % 4 == 0 and (anio % 100 != 0 or anio % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1])
    return dt.replace(year=anio, month=mes, day=dia)


def _referencia_sigue_vigente(fecha_captura: datetime | None) -> bool:
    """True si la referencia NO venció todavía (captura + vigencia > ahora)."""
    if fecha_captura is None:
        return False
    if fecha_captura.tzinfo is None:
        fecha_captura = fecha_captura.replace(tzinfo=timezone.utc)
    expira = _sumar_meses(fecha_captura, BIOMETRIC_VALIDITY_MONTHS)
    return expira > datetime.now(timezone.utc)


class GuardarEmbeddingReferenciaService:
    """Orquesta la persistencia cifrada del embedding de referencia del alumno.

    Args:
        session: sesion SQLAlchemy async (inyectada desde el endpoint).
        encryption: servicio Fernet de cifrado at-rest del embedding.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        encryption: EmbeddingEncryptionService,
    ) -> None:
        self._session = session
        self._encryption = encryption
        self._repo = EmbeddingReferenciaRepository(session)

    async def ejecutar(
        self,
        *,
        usuario_id: str,
        embedding: list[float],
        algoritmo: str = "face-api-128d",
        # C-65 task 7.3: parametros de auditoria (opcionales, backward-compatible).
        audit_repo=None,  # AuditLogSqlRepository | None
        origen: str = "enrollment",
        ip: str = "",
        user_agent: str = "",
    ) -> str:
        """Cifra y persiste el embedding de referencia; devuelve el referencia_id.

        Args:
            usuario_id: UUID del usuario autenticado (del token JWT).
            embedding: vector de 128 floats (descriptor facial 128-d).
                DATO SENSIBLE: no loguear.
            algoritmo: identificador del motor de embedding (trazabilidad).
            audit_repo: repositorio de audit log (opcional). Si se provee,
                se escribe una entrada con accion
                'enrollment.embedding_referencia.renovacion'. Si es None,
                se omite silenciosamente (backward-compatible, C-65 D6).
            origen: descripcion del origen/contexto de la solicitud (e.g.
                'perfil-web', 'api'). Se incluye en el proposito de la entrada.
            ip: IP real del cliente extraida del request HTTP. Se pasa desde
                el endpoint; no se extrae aqui para mantener el servicio
                desacoplado de FastAPI/Request.
            user_agent: User-Agent real del cliente extraido del request HTTP.

        Returns:
            ``referencia_id`` (UUID str) del nuevo registro en DB.

        Raises:
            DimensionError: si el embedding no tiene exactamente 128 dimensiones.
            EmbeddingIntegridadError: si el embedding no supera la validación de
                integridad de entrada (C-70): no-finitos, norma cero, magnitud
                absurda o el vector FAKE de desarrollo.
        """
        # 1. Validar dimension (RN-BIO: el embedding de referencia debe ser 128-d).
        if len(embedding) != EMBEDDING_DIMENSION:
            raise DimensionError(
                f"El embedding debe tener exactamente {EMBEDDING_DIMENSION} dimensiones, "
                f"recibido: {len(embedding)}."
            )

        # 1b. Integridad de entrada (C-70, regla dura #6: cliente no confiable).
        # Corta la inyección trivial ANTES de cifrar/persistir. No verifica
        # identidad (eso sería re-inferencia server-side, fuera de alcance).
        validar_integridad_embedding(embedding)

        # 2. Cifrar at-rest (el plaintext nunca se persiste).
        embedding_cifrado = self._encryption.encrypt(embedding)

        # 3a. Detectar si ya existia un embedding vigente (para distinguir alta vs renovacion).
        referencia_previa = await self._repo.obtener_vigente(usuario_id)
        tenia_referencia_previa = referencia_previa is not None

        # 3a-bis. Gate de re-captura (pedido del dueño): si la referencia previa
        # SIGUE VIGENTE (no venció), el alumno no puede rehacerla salvo que un
        # admin lo haya habilitado. El override es de UN SOLO USO: se consume acá.
        if referencia_previa is not None and _referencia_sigue_vigente(
            getattr(referencia_previa, "fecha_captura", None)
        ):
            usuario = await self._session.get(UsuarioModel, usuario_id)
            override = bool(usuario and usuario.biometria_rehacer_habilitada)
            if not override:
                raise RehacerBiometriaBloqueadoError(
                    "La referencia biométrica sigue vigente. Para rehacerla, pedile "
                    "a un administrador que te habilite una nueva captura."
                )
            # Consumir el override (una sola rehecha).
            usuario.biometria_rehacer_habilitada = False

        # 3b. Marcar embeddings anteriores como no vigentes (invariante: solo uno vigente).
        await self._repo.marcar_anteriores_no_vigentes(usuario_id)

        # 4. Crear el nuevo registro vigente (embedding ya cifrado).
        registro = await self._repo.crear(
            usuario_id=usuario_id,
            embedding_cifrado=embedding_cifrado,
            algoritmo=algoritmo,
        )

        # 5. Registrar en audit log si se inyecto el repositorio (C-65 task 7.3).
        # Se hace DESPUES de crear el registro para que el timestamp del audit
        # sea posterior a la operacion auditada (orden cronologico en la cadena).
        # NO altera la logica de embedding/custodia; es solo una escritura aditiva.
        if audit_repo is not None:
            from app.application.audit.acciones import EntidadAuditoria, ModuloAuditoria
            from app.domain.audit_chain import AuditEntry

            if tenia_referencia_previa:
                accion_audit = "enrollment.embedding_referencia.renovacion"
                proposito_audit = f"Renovacion de referencia biometrica. Origen: {origen}"
            else:
                accion_audit = "enrollment.embedding_referencia.alta"
                proposito_audit = f"Alta inicial de referencia biometrica. Origen: {origen}"

            await audit_repo.append(
                AuditEntry(
                    actor=usuario_id,
                    timestamp="",  # el trigger DB completa el timestamp real
                    ip=ip,
                    user_agent=user_agent,
                    accion=accion_audit,
                    evidencia_id=None,
                    proposito=proposito_audit,
                    # Entidad afectada = el propio alumno (dueño de la foto de
                    # referencia). Sin esto, Auditoría no podía linkear "Ver detalle"
                    # al perfil del usuario y caía al listado genérico de sesiones.
                    modulo=ModuloAuditoria.BIOMETRIA,
                    entidad=EntidadAuditoria.USUARIO,
                    entidad_id=usuario_id,
                )
            )

        return registro.id
