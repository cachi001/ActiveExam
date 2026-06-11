"""Seed de sesiones para el harness de carga PoC C-03 (Bloque 4, DESCARTABLE).

Crea en la DB las filas mínimas que k6 necesita para firmar eventos como un cliente
real: 1 usuario, 1 examen y N sesiones con ``clave_sesion`` HMAC CONOCIDA. Imprime
por stdout un JSON con ``{session_id, clave_sesion, exam_id}`` por sesión, que
``students.js`` consume para firmar (mensaje canónico HMAC-SHA256, ver README).

CONTRATO DE FIRMA (debe coincidir con el backend, signature.py + custody.py):
  mensaje = id|session_id|exam_id|tipo|severidad|ts_client|schema_version   (sep '|')
  firma   = HMAC_SHA256(key=clave_sesion.encode('utf-8'), msg=mensaje).hexdigest()
La ``clave_sesion`` es un string hex de 64 chars; se usa como bytes UTF-8 (NO se
des-hexea) — el backend hace ``clave_sesion.encode('utf-8')``.

CORRE DENTRO DEL CONTENEDOR api (tiene asyncpg + red a 'postgres'):
  docker cp poc/k6/seed.py proctoring-api-1:/tmp/seed.py
  docker exec proctoring-api-1 python /tmp/seed.py --sessions 100 > poc/k6/sessions.json

Requiere las tablas de producción (usuario/examen/sesion): aplicar antes
``alembic upgrade 0004``. Este script es DESCARTABLE.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import sys

import asyncpg


def _dsn_asyncpg(dsn: str) -> str:
    """DSN SQLAlchemy -> DSN asyncpg puro (quita el driver +asyncpg)."""
    return re.sub(r"^postgresql\+asyncpg://", "postgresql://", dsn)


async def _seed(n: int, exam_name: str) -> list[dict[str, str]]:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL no seteada en el entorno.", file=sys.stderr)
        raise SystemExit(2)

    conn = await asyncpg.connect(_dsn_asyncpg(dsn))
    try:
        # 1 usuario (id_institucional unico) y 1 examen (umbral_score NOT NULL).
        sufijo = secrets.token_hex(4)
        user_id = await conn.fetchval(
            """
            INSERT INTO usuario (id_institucional, email, roles)
            VALUES ($1, $2, '["estudiante"]'::jsonb)
            RETURNING id
            """,
            f"poc-load-{sufijo}",
            f"poc-load-{sufijo}@example.test",
        )
        exam_id = await conn.fetchval(
            """
            INSERT INTO examen (nombre, umbral_score)
            VALUES ($1, $2)
            RETURNING id
            """,
            f"{exam_name} ({sufijo})",
            60.0,
        )

        # N sesiones 'activa' con clave_sesion HMAC conocida (hex de 64 chars).
        sesiones: list[dict[str, str]] = []
        for _ in range(n):
            clave = secrets.token_hex(32)
            session_id = await conn.fetchval(
                """
                INSERT INTO sesion (user_id, exam_id, estado, clave_sesion)
                VALUES ($1, $2, 'activa', $3)
                RETURNING id
                """,
                user_id,
                exam_id,
                clave,
            )
            sesiones.append(
                {
                    "session_id": str(session_id),
                    "clave_sesion": clave,
                    "exam_id": str(exam_id),
                }
            )
        return sesiones
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed de sesiones PoC C-03 (descartable).")
    parser.add_argument("--sessions", type=int, default=100, help="Cuántas sesiones crear.")
    parser.add_argument("--exam-name", default="PoC C-03 carga", help="Nombre del examen.")
    args = parser.parse_args()

    sesiones = asyncio.run(_seed(args.sessions, args.exam_name))
    # stdout: JSON consumible por students.js. stderr: resumen humano.
    print(json.dumps(sesiones))
    print(
        f"seed: {len(sesiones)} sesiones creadas (exam_id={sesiones[0]['exam_id']}).",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
