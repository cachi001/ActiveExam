"""Medidor del panel SSE para el harness de carga PoC C-03 (Bloque 4, DESCARTABLE).

Abre N=20-40 conexiones SSE simultáneas a ``/poc/panel/stream`` (una por exam_id,
con reparto round-robin si hay menos exam_ids que paneles), registra el ``ts_rx``
LOCAL de recepción de cada evento y calcula el delta contra ``ts_backend`` (emisión,
del payload). Reporta p50/p95/p99 de la latencia de fan-out por ventana de tiempo.

Es la contraparte de medición del concern (c): mientras k6 (students.js) genera la
carga de eventos, este proceso mide la latencia evento->panel END-TO-END (incluye el
hop SSE de red, que el histograma server-side ``fanout_latency_seconds`` no ve).

USO (corre donde haya httpx + acceso al api):
  python poc/panels_asyncio.py --panels 20 \
    --exam-ids a96699fe-... b1c2... --base-url http://localhost:8000 --window 10

Este script es DESCARTABLE.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover
    raise SystemExit("Falta httpx: pip install httpx (o correr dentro del contenedor api).")


def _percentil(valores: list[float], p: float) -> float:
    """Percentil simple (nearest-rank) sobre una lista de latencias en ms."""
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    k = max(0, min(len(ordenados) - 1, int(round((p / 100.0) * len(ordenados) + 0.5)) - 1))
    return ordenados[k]


class Acumulador:
    """Acumula deltas (ms) y los vacía al reportar por ventana."""

    def __init__(self) -> None:
        self._deltas: list[float] = []
        self.total = 0

    def registrar(self, delta_ms: float) -> None:
        self._deltas.append(delta_ms)
        self.total += 1

    def reportar_y_limpiar(self) -> tuple[int, float, float, float]:
        n = len(self._deltas)
        p50 = _percentil(self._deltas, 50)
        p95 = _percentil(self._deltas, 95)
        p99 = _percentil(self._deltas, 99)
        self._deltas = []
        return n, p50, p95, p99


async def _panel(idx: int, base_url: str, exam_id: str, acc: Acumulador) -> None:
    """Una conexión SSE: parsea ``data:`` y registra el delta ts_backend->ts_rx_local."""
    url = f"{base_url}/poc/panel/stream?exam_id={exam_id}"
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", url) as resp:
            async for linea in resp.aiter_lines():
                if not linea.startswith("data:"):
                    continue  # comentarios SSE (": keep-alive", ": conectado")
                ts_rx = datetime.now(timezone.utc)
                try:
                    data = json.loads(linea[len("data:"):].strip())
                except (json.JSONDecodeError, ValueError):
                    continue
                ts_backend_str = data.get("ts_backend")
                if not ts_backend_str:
                    continue
                try:
                    ts_backend = datetime.fromisoformat(ts_backend_str)
                    delta_ms = (ts_rx - ts_backend).total_seconds() * 1000.0
                    if delta_ms >= 0:
                        acc.registrar(delta_ms)
                except (ValueError, TypeError):
                    continue


async def _reporter(acc: Acumulador, ventana_s: float) -> None:
    """Imprime p50/p95/p99 de la ventana cada ``ventana_s`` segundos."""
    while True:
        await asyncio.sleep(ventana_s)
        n, p50, p95, p99 = acc.reportar_y_limpiar()
        marca = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(
            f"[{marca}] ventana={ventana_s:.0f}s  n={n:<5}  "
            f"p50={p50:7.2f}ms  p95={p95:7.2f}ms  p99={p99:7.2f}ms  (acum total={acc.total})",
            flush=True,
        )


async def _main(args: argparse.Namespace) -> None:
    acc = Acumulador()
    exam_ids = args.exam_ids
    # Reparto round-robin: panel i observa exam_ids[i % len].
    tareas = [
        asyncio.create_task(_panel(i, args.base_url, exam_ids[i % len(exam_ids)], acc))
        for i in range(args.panels)
    ]
    tareas.append(asyncio.create_task(_reporter(acc, args.window)))
    print(
        f"panels: {args.panels} conexiones SSE a {args.base_url} "
        f"sobre {len(exam_ids)} exam_id(s). Ventana {args.window}s. Ctrl-C para cortar.",
        flush=True,
    )
    try:
        await asyncio.gather(*tareas)
    except asyncio.CancelledError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Medidor de paneles SSE PoC C-03 (descartable).")
    parser.add_argument("--panels", type=int, default=20, help="Cuántas conexiones SSE abrir.")
    parser.add_argument("--exam-ids", nargs="+", required=True, help="exam_id(s) a observar.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="URL base del api.")
    parser.add_argument("--window", type=float, default=10.0, help="Ventana de reporte (s).")
    try:
        asyncio.run(_main(parser.parse_args()))
    except KeyboardInterrupt:
        print("\npanels: cortado por el usuario.")


if __name__ == "__main__":
    main()
