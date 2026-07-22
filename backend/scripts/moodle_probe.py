"""Sonda READ-ONLY del Web Service de Moodle (C-73 §8.1 / prep §7.3-7.4).

NO escribe ninguna nota. Valida que el token funcione y mapea:
  1. core_webservice_get_site_info → sitename, usuario del token, y la LISTA de
     funciones habilitadas para ese token (esto responde 8.1: qué WS hay disponibles).
  2. Resolución de identidad (read-only) con el MISMO código de producción
     (MoodleRestClient.lookup_userid_by_email / _by_idnumber) para un email de prueba.

El token NUNCA se hardcodea ni se loguea: se lee del entorno. Correr así (PowerShell):

    $env:MOODLE_BASE_URL   = "https://campustest.frm.utn.edu.ar"
    $env:MOODLE_WS_TOKEN   = "<tu token>"      # NO lo pegues en ningún archivo
    $env:MOODLE_PROBE_EMAIL = "juancruzrobledo46@gmail.com"   # opcional
    python scripts/moodle_probe.py

Salida: imprime el resumen. El token se enmascara siempre (solo longitud).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import httpx

# Permite `python scripts/moodle_probe.py` desde backend/: agrega la raíz del
# backend (padre de scripts/) al path para que `app` sea importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.moodle.client import MoodleClientConfig, MoodleRestClient


def _mask(token: str) -> str:
    return f"<{len(token)} chars>" if token else "<vacío>"


async def _site_info(base_url: str, token: str) -> dict:
    """core_webservice_get_site_info — read-only, confirma token + lista funciones."""
    url = f"{base_url.rstrip('/')}/webservice/rest/server.php"
    params = {
        "wstoken": token,
        "wsfunction": "core_webservice_get_site_info",
        "moodlewsrestformat": "json",
    }
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.post(url, data=params)
        resp.raise_for_status()
        return resp.json()


async def main() -> int:
    base_url = os.environ.get("MOODLE_BASE_URL", "").strip()
    token = os.environ.get("MOODLE_WS_TOKEN", "").strip()
    probe_email = os.environ.get("MOODLE_PROBE_EMAIL", "").strip()

    print(f"base_url = {base_url or '<vacío>'}")
    print(f"token    = {_mask(token)}")
    if not base_url or not token:
        print("ERROR: seteá MOODLE_BASE_URL y MOODLE_WS_TOKEN en el entorno.")
        return 2

    # 1) Site info (read-only)
    try:
        info = await _site_info(base_url, token)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR llamando get_site_info: {type(exc).__name__}: {exc}")
        return 1

    if "exception" in info:  # Moodle devuelve {exception, errorcode, message}
        print("TOKEN RECHAZADO por Moodle:")
        print(f"  errorcode: {info.get('errorcode')}")
        print(f"  message:   {info.get('message')}")
        return 1

    print("\n=== SITE INFO (token válido) ===")
    print(f"  sitename : {info.get('sitename')}")
    print(f"  usuario  : {info.get('fullname')} (username={info.get('username')}, userid={info.get('userid')})")
    print(f"  release  : {info.get('release')}")

    funciones = sorted(f.get("name", "") for f in info.get("functions", []))
    print(f"\n=== FUNCIONES HABILITADAS PARA EL TOKEN ({len(funciones)}) ===")
    for nombre in funciones:
        print(f"  - {nombre}")

    # ¿Está la de write-back y las de identidad que usa el proctoring?
    requeridas = {
        "core_grades_update_grades": "write-back de nota (7.3)",
        "core_user_get_users_by_field": "resolución de identidad idnumber/email (7.4)",
    }
    print("\n=== CHEQUEO DE FUNCIONES QUE NECESITA EL PROCTORING ===")
    for fn, para in requeridas.items():
        estado = "✅ presente" if fn in funciones else "❌ FALTA"
        print(f"  {estado}  {fn}  — {para}")

    # 2) Identidad read-only con el código de producción (si hay email de prueba)
    if probe_email:
        client = MoodleRestClient(
            config=MoodleClientConfig(base_url=base_url, ws_token=token, courseid=0, cmid=0)
        )
        try:
            uid = await client.lookup_userid_by_email(probe_email)
            print(f"\n=== IDENTIDAD (read-only) ===")
            print(f"  email {probe_email} → userid {uid if uid is not None else '<no resuelto>'}")
        except Exception as exc:  # noqa: BLE001
            print(f"\n  lookup_userid_by_email falló: {type(exc).__name__}: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
