"""Sincronización del banco de preguntas desde Moodle (C-74 §9.3).

Llama a la REST API de Moodle para importar categorías y preguntas del banco
de un curso. Es IDEMPOTENTE: re-sincronizar el mismo curso no duplica filas.

Endpoint Moodle usado:
  - ``core_question_get_bank_categories``: árbol de categorías del banco de un
    curso. Devuelve lista plana con campo ``parent`` para reconstruir la jerarquía.
  - ``local_wsmanager_get_questions_for_bank`` (si disponible) o ningún endpoint
    estándar para preguntas individuales del banco. Ver nota abajo.

Nota sobre preguntas:
  Moodle no expone un endpoint estándar para listar preguntas del banco de
  preguntas por categoría antes de Moodle 4.3 (``core_question_get_questions``).
  Esta implementación sincroniza SOLO las categorías en la versión inicial. Las
  preguntas se importan vía XML (flujo existente). El servicio retorna
  ``preguntas_nuevas`` y ``preguntas_actualizadas`` siempre como 0 hasta que se
  integre ese endpoint.
"""

from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.exam_content import (
    CategoriaPreguntaModel,
)


async def sync_banco_desde_moodle(
    *,
    db: AsyncSession,
    courseid: int,
    materia_id: str,
    token: str,
    base_url: str,
) -> dict:
    """Sincroniza categorías del banco de preguntas de un curso Moodle.

    Args:
        db: sesión de base de datos activa.
        courseid: ID del curso en Moodle.
        materia_id: ID de la materia en ActiveExam (UUID).
        token: token Moodle del docente (o institucional).
        base_url: URL base del campus Moodle (ej. ``https://campus.ejemplo.com``).

    Returns:
        dict con claves:
          - ``categorias_creadas``: int — nuevas categorías insertadas.
          - ``preguntas_nuevas``: int — siempre 0 (ver nota del módulo).
          - ``preguntas_actualizadas``: int — siempre 0 (ver nota del módulo).

    Raises:
        MoodleSyncError: si Moodle responde con error o la red falla.
    """
    categorias = await _fetch_bank_categories(
        base_url=base_url,
        token=token,
        courseid=courseid,
    )

    categorias_creadas = await _upsert_categorias(
        db=db,
        materia_id=materia_id,
        categorias_moodle=categorias,
    )

    return {
        "categorias_creadas": categorias_creadas,
        "preguntas_nuevas": 0,
        "preguntas_actualizadas": 0,
    }


class MoodleSyncError(Exception):
    """Error al sincronizar el banco desde Moodle."""


async def _post_ws(
    *,
    base_url: str,
    token: str,
    wsfunction: str,
    data: dict[str, str],
) -> list | dict | None:
    """Llamada POST a la REST API de Moodle. Eleva MoodleSyncError ante cualquier
    fallo de red, HTTP >= 400, o error devuelto por el WS (``exception`` en JSON).
    """
    url = f"{base_url.rstrip('/')}/webservice/rest/server.php"
    payload = {
        "wstoken": token,
        "wsfunction": wsfunction,
        "moodlewsrestformat": "json",
        **data,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, data=payload)
    except Exception as exc:
        raise MoodleSyncError(f"Error de red al llamar {wsfunction}: {exc}") from exc

    if response.status_code >= 400:
        raise MoodleSyncError(
            f"Moodle devolvió HTTP {response.status_code} en {wsfunction}"
        )

    if not response.content.strip():
        return None

    try:
        body = response.json()
    except Exception as exc:
        raise MoodleSyncError(
            f"Respuesta no-JSON de Moodle en {wsfunction}: {exc}"
        ) from exc

    if isinstance(body, dict) and ("exception" in body or "errorcode" in body):
        errorcode = body.get("errorcode", "unknown")
        message = body.get("message", "")
        raise MoodleSyncError(
            f"Moodle WS error en {wsfunction} ({errorcode}): {message}"
        )

    return body


async def _fetch_bank_categories(
    *,
    base_url: str,
    token: str,
    courseid: int,
) -> list[dict]:
    """Obtiene la lista de categorías del banco de preguntas de un curso.

    Llama a ``core_question_get_bank_categories``. Devuelve una lista plana
    de dicts con al menos ``id``, ``name`` y ``parent`` (0 = raíz del curso).
    Si el endpoint no existe (Moodle < 4.3), devuelve lista vacía sin error.
    """
    try:
        result = await _post_ws(
            base_url=base_url,
            token=token,
            wsfunction="core_question_get_bank_categories",
            data={"courseid": str(courseid)},
        )
    except MoodleSyncError as exc:
        # El endpoint puede no existir en versiones más antiguas de Moodle.
        # Registramos el fallo pero no abortamos — retornamos vacío.
        _msg = str(exc).lower()
        if "invalidfunction" in _msg or "unknown function" in _msg or "nosuchfunction" in _msg:
            return []
        raise

    if not result:
        return []

    # Normalizar: puede venir como list o como dict con key 'categories'
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return result.get("categories", [])
    return []


async def _upsert_categorias(
    *,
    db: AsyncSession,
    materia_id: str,
    categorias_moodle: list[dict],
) -> int:
    """Upsert idempotente de categorías del banco de preguntas.

    Es ADITIVO y NO DESTRUCTIVO: crea las categorías que faltan y nunca renombra,
    mueve ni borra las que ya están. El árbol que organizó el docente es suyo.

    Identidad de una categoría, en orden (0058):

    1. ``moodle_category_id`` — el ancla fuerte. Sobrevive a que el docente le
       cambie el nombre localmente. Antes el match era solo por nombre, así que
       un rename hacía que el sync no la reconociera y creara un duplicado vacío.
    2. ``(moodle_nombre_origen | nombre, padre_id)`` — para las categorías que
       vienen de antes de 0058 y todavía no tienen el id de Moodle sellado. Al
       encontrarlas se les sella, y de ahí en más entran por el camino 1.
    3. No hay match → se crea.

    El árbol se procesa de raíz a hojas: primero las categorías con parent=0
    (o cuyo padre ya fue procesado), luego sus hijos. Hasta 10 pasadas para
    soportar jerarquías profundas (en la práctica 2-3 niveles).

    Returns:
        Número de categorías NUEVAS creadas.
    """
    if not categorias_moodle:
        return 0

    # moodle_id → id interno ya resuelto (para colgar los hijos de la jerarquía)
    moodle_to_interno: dict[int, str] = {}

    existentes_result = await db.execute(
        select(CategoriaPreguntaModel).where(
            CategoriaPreguntaModel.materia_id == materia_id
        )
    )
    existentes = list(existentes_result.scalars().all())

    # Índice fuerte: id de Moodle → fila local.
    por_moodle_id: dict[int, CategoriaPreguntaModel] = {
        row.moodle_category_id: row
        for row in existentes
        if row.moodle_category_id is not None
    }
    # Índice de compatibilidad: (nombre de origen, padre) → fila local, solo para
    # las que todavía no tienen el id de Moodle sellado.
    por_origen: dict[tuple[str, str | None], CategoriaPreguntaModel] = {
        (row.moodle_nombre_origen or row.nombre, row.categoria_padre_id): row
        for row in existentes
        if row.moodle_category_id is None
    }

    creadas = 0
    pendientes = list(categorias_moodle)
    max_pasadas = 10

    for _ in range(max_pasadas):
        if not pendientes:
            break
        siguiente_ronda = []
        for cat in pendientes:
            moodle_id = cat.get("id")
            nombre = (cat.get("name") or "").strip()
            if not nombre:
                continue
            parent_moodle_id = cat.get("parent", 0)

            # Resolver padre interno
            if parent_moodle_id == 0:
                padre_interno = None
            elif parent_moodle_id in moodle_to_interno:
                padre_interno = moodle_to_interno[parent_moodle_id]
            else:
                # Padre no procesado aún → dejar para la próxima ronda
                siguiente_ronda.append(cat)
                continue

            # 1. Ancla fuerte: ya la conocemos por su id de Moodle.
            if moodle_id is not None and moodle_id in por_moodle_id:
                # No se toca nada: ni nombre (puede estar renombrada a propósito)
                # ni padre (puede estar reubicada a propósito).
                moodle_to_interno[moodle_id] = por_moodle_id[moodle_id].id
                continue

            # 2. Compatibilidad: existe sin id sellado → sellarlo y reutilizar.
            clave = (nombre, padre_interno)
            if clave in por_origen:
                fila = por_origen.pop(clave)
                if moodle_id is not None:
                    fila.moodle_category_id = moodle_id
                    por_moodle_id[moodle_id] = fila
                if fila.moodle_nombre_origen is None:
                    fila.moodle_nombre_origen = nombre
                await db.flush()
                if moodle_id is not None:
                    moodle_to_interno[moodle_id] = fila.id
                continue

            # 3. Nueva.
            nueva = CategoriaPreguntaModel(
                materia_id=materia_id,
                nombre=nombre,
                categoria_padre_id=padre_interno,
                moodle_category_id=moodle_id,
                moodle_nombre_origen=nombre,
            )
            db.add(nueva)
            await db.flush()  # para obtener el id generado por el servidor

            if moodle_id is not None:
                por_moodle_id[moodle_id] = nueva
                moodle_to_interno[moodle_id] = nueva.id
            creadas += 1

        pendientes = siguiente_ronda

    return creadas
