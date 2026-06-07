"""Modelos ORM slim — variantes de tablas con schema diferente al full (c-57).

Este modulo define modelos ORM para el modulo slim de Railway que difieren
del schema del full. SOLO se importa desde codigo slim (main_slim, slim_wiring,
db_photo_storage). NUNCA importar desde __init__.py (evitar conflicto de tabla
duplicada en la misma MetaData).

DISENO (c-57, D1):
  ``FotoReferenciaSlimModel`` mapea a la misma tabla ``foto_referencia`` que
  ``FotoReferenciaModel``, pero con columnas distintas:
    - Full:  uri_storage, bucket (punteros a MinIO)
    - Slim:  foto_bytes BYTEA (contenido directo en Postgres)

  Son incompatibles — en cada entorno existe UNA de las dos variantes fisicas:
    - Railway (slim): solo foto_bytes (migrado por 0008 slim)
    - Full (produccion): solo uri_storage + bucket (migrado por 0007 main)

IMPORTANTE: este archivo NO debe importarse en la metadata del full (no incluir
en __init__.py) porque causaria InvalidRequestError de SQLAlchemy (tabla
definida dos veces en la misma MetaData instance).

Para evitar el conflicto: este modelo usa una MetaData separada (la Base del
slim) cuando corre en el slim. En la practica, el slim importa SOLO este
modulo (no transactional.py) para foto_referencia.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, LargeBinary, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.persistence.base import Base


class FotoReferenciaSlimModel(Base):
    """Foto de perfil del alumno — variante slim (c-57, D1).

    En el modulo slim (Railway / Postgres estandar), la foto se almacena
    directamente como BYTEA en la columna ``foto_bytes``, sin MinIO.

    NO importar en el mismo proceso que ``FotoReferenciaModel`` (mismo nombre
    de tabla, metadata diferente). Usar solo en el slim.

    NOTA: si este modelo y FotoReferenciaModel se importan en el mismo proceso
    (ej. tests del full), SQLAlchemy lanza InvalidRequestError. La solucion es
    importar SOLO uno de los dos segun el entorno.
    """

    __tablename__ = "foto_referencia"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    usuario_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False
    )
    foto_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    hash_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    vigente: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
