"""Modelos ORM activeexam — variantes de tablas con schema diferente al full (c-57).

ESTADO ACTUAL: no queda ninguna variante propia.

``FotoReferenciaActiveExamModel`` existía porque ``FotoReferenciaModel`` declaraba
las columnas de MinIO (``uri_storage``, ``bucket``) y acá hacía falta la variante
con ``foto_bytes``. Nunca se llegó a importar en ningún lado (el guardado de la
foto usa SQL Core en ``db_photo_storage``), y mientras tanto el modelo "bueno"
seguía describiendo una tabla que no existe en ninguna base viva.

Ahora ``FotoReferenciaModel`` describe la tabla real (la que crea la migración
0008) y esta es un alias, para no tener dos definiciones de la misma tabla en la
misma MetaData — que es justamente lo que hacía saltar
``InvalidRequestError`` al importar los dos módulos en un mismo proceso.

Si vuelve MinIO, la variante que va a hacer falta es la del bucket, y el lugar
para declararla es este archivo. Ver el docstring de ``FotoReferenciaModel``.
"""

from __future__ import annotations

from app.infrastructure.persistence.models.transactional import FotoReferenciaModel

#: Alias histórico. Mismo modelo: la tabla real guarda la foto en ``foto_bytes``.
FotoReferenciaActiveExamModel = FotoReferenciaModel

__all__ = ["FotoReferenciaActiveExamModel"]
