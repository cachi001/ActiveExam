"""Avalancha LTI: N alumnos entrando por el link de Moodle en el mismo minuto.

Por qué existe
--------------
El día del examen nadie entra escalonado: el docente publica el link y 70 a 100
alumnos hacen click casi a la vez. Ese camino (``/lti/login`` → ``/lti/launch``)
no lo toca el harness de k6, que arranca con un ``POST /auth/login`` ya resuelto.
Y es el camino donde ya apareció un incidente: bcrypt corría sincrónico dentro de
una corrutina y congelaba el servidor **entero** ~17 s con 70 altas.

Qué mide
--------
1. **Cuánto tarda cada launch** y cuánto tarda la avalancha completa.
2. **Si el servidor se congela para todos los demás**: un hilo *canario* pega a un
   endpoint barato cada 200 ms durante toda la corrida. Si el bucle de eventos se
   bloquea, el canario lo ve aunque los launches "terminen bien". Esta es la
   medición que importa: un launch lento afecta a quien entra; un bucle bloqueado
   afecta a todos los que ya estaban rindiendo.

Cómo se corre
-------------
Corre DENTRO del contenedor del backend, que ya tiene ``httpx``, ``PyJWT`` y
``cryptography``, y desde donde el propio backend puede resolver el JWKS falso en
``localhost``::

    docker cp tools/carga/avalancha-lti.py activeexam-dev-backend-1:/app/
    docker exec -e DATABASE_URL=... activeexam-dev-backend-1 \
        python /app/avalancha-lti.py --alumnos 70

La plataforma falsa
-------------------
``jwks_uri`` se guarda **por deployment**, así que alcanza con registrar una fila
en ``lti_deployment_confiable`` apuntando al JWKS que sirve este mismo script. No
se toca ninguna plataforma real. La fila se borra al terminar (``--conservar`` la
deja para inspeccionarla).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

CLAIM_DEPLOYMENT_ID = "https://purl.imsglobal.org/spec/lti/claim/deployment_id"
CLAIM_CONTEXT = "https://purl.imsglobal.org/spec/lti/claim/context"
CLAIM_ROLES = "https://purl.imsglobal.org/spec/lti/claim/roles"
ROL_ESTUDIANTE = "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"

KID = "avalancha-lti-kid"


# ---------------------------------------------------------------------------
# Plataforma falsa: par de claves + JWKS servido por HTTP
# ---------------------------------------------------------------------------


def _generar_clave() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks_de(clave: rsa.RSAPrivateKey) -> dict:
    numeros = clave.public_key().public_numbers()

    def b64(n: int) -> str:
        import base64

        largo = (n.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(n.to_bytes(largo, "big")).decode().rstrip("=")

    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": KID,
                "n": b64(numeros.n),
                "e": b64(numeros.e),
            }
        ]
    }


class _ServidorJwks(threading.Thread):
    """Sirve el JWKS de la plataforma falsa. Cuenta cuántas veces se lo piden.

    Ese contador no es decorativo: si el backend cachea el JWKS se pide una vez;
    si lo baja en CADA launch, se pide N veces, y ahí cada launch paga una ida y
    vuelta HTTP completa.
    """

    def __init__(self, jwks: dict, puerto: int, demora_ms: int):
        super().__init__(daemon=True)
        self.jwks = jwks
        self.puerto = puerto
        self.demora_ms = demora_ms
        self.pedidos = 0
        self._servidor: HTTPServer | None = None

    def run(self) -> None:
        padre = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                padre.pedidos += 1
                # Moodle real no está en localhost: la demora simula la ida y
                # vuelta a un campus remoto, que es lo que paga cada launch.
                if padre.demora_ms:
                    time.sleep(padre.demora_ms / 1000)
                cuerpo = json.dumps(padre.jwks).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def log_message(self, *_args):  # silencio
                return

        self._servidor = HTTPServer(("0.0.0.0", self.puerto), Handler)
        self._servidor.serve_forever()

    def parar(self) -> None:
        if self._servidor is not None:
            self._servidor.shutdown()


# ---------------------------------------------------------------------------
# Registro de la plataforma falsa en la allowlist
# ---------------------------------------------------------------------------


async def _registrar_deployment(db_url: str, *, iss: str, deployment_id: str,
                                client_id: str, jwks_uri: str) -> str:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    eng = create_async_engine(db_url, future=True)
    try:
        async with eng.begin() as conn:
            fila = await conn.execute(
                text(
                    "INSERT INTO lti_deployment_confiable "
                    "(iss, deployment_id, client_id, jwks_uri, activo) "
                    "VALUES (:iss, :dep, :cli, :jwks, true) RETURNING id"
                ),
                {"iss": iss, "dep": deployment_id, "cli": client_id, "jwks": jwks_uri},
            )
            return fila.scalar_one()
    finally:
        await eng.dispose()


async def _borrar_deployment(db_url: str, fila_id: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    eng = create_async_engine(db_url, future=True)
    try:
        async with eng.begin() as conn:
            await conn.execute(
                text("DELETE FROM lti_deployment_confiable WHERE id = :id"),
                {"id": fila_id},
            )
    finally:
        await eng.dispose()


# ---------------------------------------------------------------------------
# El canario: żse congeló el servidor para todos los demás?
# ---------------------------------------------------------------------------


class Canario(threading.Thread):
    def __init__(self, base: str, cada_ms: int = 200):
        super().__init__(daemon=True)
        self.base = base
        self.cada_ms = cada_ms
        self.latencias: list[float] = []
        self._parar = threading.Event()

    def run(self) -> None:
        with httpx.Client(timeout=60) as cli:
            while not self._parar.is_set():
                t0 = time.perf_counter()
                try:
                    cli.get(f"{self.base}/api/v1/lti/jwks")
                    self.latencias.append((time.perf_counter() - t0) * 1000)
                except Exception:  # noqa: BLE001 — un timeout ES el dato
                    self.latencias.append(60_000)
                time.sleep(self.cada_ms / 1000)

    def parar(self) -> None:
        self._parar.set()


# ---------------------------------------------------------------------------
# Un alumno entrando por el link de Moodle
# ---------------------------------------------------------------------------


def _id_token(clave, *, iss, client_id, deployment_id, nonce, sub, nombre, email,
              context_id) -> str:
    ahora = datetime.now(timezone.utc)
    claims = {
        "iss": iss,
        "aud": client_id,
        "sub": sub,
        "nonce": nonce,
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(minutes=5)).timestamp()),
        "name": nombre,
        "email": email,
        CLAIM_DEPLOYMENT_ID: deployment_id,
        CLAIM_ROLES: [ROL_ESTUDIANTE],
        CLAIM_CONTEXT: {"id": context_id, "label": "CARGA", "title": "Curso de carga"},
    }
    return jwt.encode(claims, clave, algorithm="RS256", headers={"kid": KID})


async def _un_alumno(cli: httpx.AsyncClient, *, base, clave, iss, client_id,
                     deployment_id, context_id, n: int) -> tuple[float, int, str]:
    sub = f"carga-lti-{uuid.uuid4().hex[:12]}"
    t0 = time.perf_counter()

    login = await cli.post(
        f"{base}/api/v1/lti/login",
        data={
            "iss": iss,
            "login_hint": sub,
            "target_link_uri": f"{base}/api/v1/lti/launch",
            "client_id": client_id,
            "lti_deployment_id": deployment_id,
        },
        follow_redirects=False,
    )
    if login.status_code != 302:
        return (time.perf_counter() - t0) * 1000, login.status_code, "login"

    query = parse_qs(urlparse(login.headers["location"]).query)
    state, nonce = query["state"][0], query["nonce"][0]

    token = _id_token(
        clave, iss=iss, client_id=client_id, deployment_id=deployment_id,
        nonce=nonce, sub=sub, nombre=f"Alumno Carga {n}",
        email=f"{sub}@carga.local", context_id=context_id,
    )
    launch = await cli.post(
        f"{base}/api/v1/lti/launch",
        data={"id_token": token, "state": state},
        follow_redirects=False,
    )
    return (time.perf_counter() - t0) * 1000, launch.status_code, "launch"


# ---------------------------------------------------------------------------


async def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", default=os.environ.get("BASE", "http://localhost:8000"))
    p.add_argument("--alumnos", type=int, default=70)
    p.add_argument("--puerto-jwks", type=int, default=9401)
    p.add_argument(
        "--jwks-demora-ms", type=int, default=80,
        help="Demora simulada del campus remoto al servir su JWKS (0 = instantáneo)",
    )
    p.add_argument("--conservar", action="store_true",
                   help="No borrar la plataforma falsa al terminar")
    args = p.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Falta DATABASE_URL")
        return 2

    iss = f"http://plataforma-carga-{uuid.uuid4().hex[:8]}.local"
    deployment_id = f"dep-{uuid.uuid4().hex[:8]}"
    client_id = f"cli-{uuid.uuid4().hex[:8]}"
    context_id = f"ctx-{uuid.uuid4().hex[:8]}"

    clave = _generar_clave()
    servidor = _ServidorJwks(_jwks_de(clave), args.puerto_jwks, args.jwks_demora_ms)
    servidor.start()
    time.sleep(0.3)

    jwks_uri = f"http://localhost:{args.puerto_jwks}/jwks"
    fila_id = await _registrar_deployment(
        db_url, iss=iss, deployment_id=deployment_id,
        client_id=client_id, jwks_uri=jwks_uri,
    )
    print(f"Plataforma falsa registrada: {iss} (fila {fila_id})")
    print(f"JWKS en {jwks_uri} con {args.jwks_demora_ms} ms de demora simulada\n")

    canario = Canario(args.base)
    canario.start()
    # Línea de base: cómo responde el servidor ANTES de la avalancha.
    time.sleep(2)
    base_canario = list(canario.latencias)

    print(f"Lanzando {args.alumnos} alumnos a la vez…")
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=120) as cli:
        resultados = await asyncio.gather(*[
            _un_alumno(
                cli, base=args.base, clave=clave, iss=iss, client_id=client_id,
                deployment_id=deployment_id, context_id=context_id, n=i,
            )
            for i in range(args.alumnos)
        ], return_exceptions=True)
    total_seg = time.perf_counter() - t0

    time.sleep(1)
    canario.parar()
    durante = canario.latencias[len(base_canario):]

    ok, fallidos, latencias = 0, {}, []
    for r in resultados:
        if isinstance(r, Exception):
            fallidos[f"excepcion: {type(r).__name__}"] = fallidos.get(
                f"excepcion: {type(r).__name__}", 0) + 1
            continue
        ms, codigo, etapa = r
        latencias.append(ms)
        # 302 = launch válido. Una cuenta NUEVA redirige a la pantalla de
        # confirmación; una ya existente, al frontend con su token. Los dos son
        # el camino feliz.
        if codigo == 302:
            ok += 1
        else:
            fallidos[f"{etapa} HTTP {codigo}"] = fallidos.get(f"{etapa} HTTP {codigo}", 0) + 1

    def pct(xs, q):
        return statistics.quantiles(xs, n=100)[q - 1] if len(xs) > 1 else (xs[0] if xs else 0)

    print(f"\n{'=' * 62}")
    print(f"AVALANCHA LTI — {args.alumnos} alumnos")
    print(f"{'=' * 62}")
    print(f"Tiempo total de la avalancha : {total_seg:.1f} s")
    print(f"Launches OK (302)            : {ok}/{args.alumnos}")
    if fallidos:
        for motivo, n in sorted(fallidos.items()):
            print(f"  fallidos — {motivo}: {n}")
    if latencias:
        print(f"Latencia por alumno          : med={statistics.median(latencias):.0f} ms  "
              f"p95={pct(latencias, 95):.0f} ms  max={max(latencias):.0f} ms")
    print(f"Pedidos al JWKS              : {servidor.pedidos} "
          f"({'SIN cache: uno por launch' if servidor.pedidos >= args.alumnos else 'cacheado'})")
    print("\n-- El canario (todo lo demás del sistema) --")
    if base_canario:
        print(f"Antes de la avalancha        : med={statistics.median(base_canario):.0f} ms  "
              f"max={max(base_canario):.0f} ms")
    if durante:
        print(f"DURANTE la avalancha         : med={statistics.median(durante):.0f} ms  "
              f"max={max(durante):.0f} ms")
        # Un segundo entero sin atender es el corte: por debajo de eso hay
        # contención normal de base con N escrituras concurrentes, que no es lo
        # mismo que el bucle de eventos bloqueado. La primera versión avisaba con
        # 5x la línea de base y gritaba ante 311 ms, que no es un congelamiento.
        if max(durante) > 1000:
            print("\n  ⚠️  El servidor se degradó para TODOS mientras entraban los alumnos.")
            print("      No es que el login sea lento: es que bloquea el bucle de eventos.")
    print()

    servidor.parar()
    if not args.conservar:
        await _borrar_deployment(db_url, fila_id)
        print("Plataforma falsa borrada.")
    else:
        print(f"Plataforma falsa CONSERVADA (fila {fila_id}) — borrala a mano.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
