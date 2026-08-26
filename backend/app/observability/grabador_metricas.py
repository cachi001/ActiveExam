"""Graba `/metrics` durante un examen y deja un archivo para revisar después (c-78 §16.3b).

`/metrics` ya está protegido y expone lo que hace falta, pero nadie lo guarda: Render
free no corre un Prometheus al lado, así que la serie vive en la memoria del proceso y
se pierde en cada reinicio. Si durante el examen algo va mal, la única evidencia es lo
que alguien haya alcanzado a mirar en vivo.

Esta es la versión mínima que resuelve eso sin infraestructura nueva: **solo stdlib**,
corre desde cualquier máquina con Python y deja un `.jsonl` por examen — una línea por
muestra, más un resumen al cerrar.

    python backend/app/observability/grabador_metricas.py \\
        https://actibeexam.onrender.com <TOKEN> --cada 15 --salida examen.jsonl

Se corta con Ctrl+C y ahí imprime el resumen. El token es el `METRICS_TOKEN` del
entorno; NO se escribe en el archivo de salida (el repo es público y el archivo se
comparte para analizarlo).

OJO con varios workers: `prometheus_client` cuenta por PROCESO, así que cada scrape
cae en un worker al azar y ve solo lo suyo. En producción hoy hay un solo proceso y
el número es el total; en dev, que corre con `--workers 4`, las cifras son parciales
y saltan entre muestras. Interpretarlas como el total del servicio sería un error.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Muestra:
    """Una foto de los contadores en un instante."""

    momento: float
    requests_total: int
    requests_5xx: int
    memoria_bytes: float
    cpu_segundos: float


@dataclass(frozen=True)
class Diferencia:
    """Lo que pasó ENTRE dos fotos, que es lo único que se puede leer como tasa."""

    requests_por_segundo: float
    cpu_usada: float
    reinicio_detectado: bool


def _valor(linea: str) -> float:
    try:
        return float(linea.rsplit(" ", 1)[1])
    except (IndexError, ValueError):
        return 0.0


def _status_de(linea: str) -> str:
    marca = 'status="'
    inicio = linea.find(marca)
    if inicio == -1:
        return ""
    inicio += len(marca)
    return linea[inicio : linea.find('"', inicio)]


def parsear_exposicion(texto: str, momento: float | None = None) -> Muestra:
    """Lee el formato de exposición de Prometheus y saca las cuatro series que
    importan durante un examen.

    Tolerante a propósito: comentarios, líneas cortadas y un scrape vacío devuelven
    ceros en vez de romper. Perder una muestra no puede terminar la grabación.
    """
    requests_total = 0.0
    requests_5xx = 0.0
    memoria = 0.0
    cpu = 0.0

    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue

        if linea.startswith("http_requests_total"):
            valor = _valor(linea)
            requests_total += valor
            # Solo 5xx: los 4xx son ruido normal (token vencido, ruta inexistente) y
            # mezclarlos haría que el número deje de alarmar cuando importa.
            if _status_de(linea).startswith("5"):
                requests_5xx += valor
        elif linea.startswith("process_resident_memory_bytes"):
            memoria = _valor(linea)
        elif linea.startswith("process_cpu_seconds_total"):
            cpu = _valor(linea)

    return Muestra(
        momento=time.time() if momento is None else momento,
        requests_total=int(requests_total),
        requests_5xx=int(requests_5xx),
        memoria_bytes=memoria,
        cpu_segundos=cpu,
    )


def diferencia_entre(antes: Muestra, despues: Muestra) -> Diferencia:
    """Convierte dos fotos de contadores acumulados en tasas por segundo.

    Si los contadores BAJARON, el proceso se reinició (Render lo hace solo) y los
    acumuladores volvieron a cero: la resta daría negativa. Se reporta como reinicio
    y tasa 0, que es lo honesto — no sabemos qué pasó en el hueco.
    """
    transcurrido = despues.momento - antes.momento
    reinicio = (
        despues.requests_total < antes.requests_total
        or despues.cpu_segundos < antes.cpu_segundos
    )

    if transcurrido <= 0 or reinicio:
        return Diferencia(
            requests_por_segundo=0.0, cpu_usada=0.0, reinicio_detectado=reinicio
        )

    return Diferencia(
        requests_por_segundo=(despues.requests_total - antes.requests_total) / transcurrido,
        cpu_usada=(despues.cpu_segundos - antes.cpu_segundos) / transcurrido,
        reinicio_detectado=False,
    )


def resumir(muestras: list[Muestra]) -> dict:
    """Lo que uno quiere saber al terminar: cuánto aguantó, cuánta memoria usó y si
    falló algo."""
    if not muestras:
        return {"muestras": 0}

    pico_rps = 0.0
    pico_cpu = 0.0
    reinicios = 0
    for antes, despues in zip(muestras, muestras[1:]):
        d = diferencia_entre(antes, despues)
        pico_rps = max(pico_rps, d.requests_por_segundo)
        pico_cpu = max(pico_cpu, d.cpu_usada)
        reinicios += int(d.reinicio_detectado)

    return {
        "muestras": len(muestras),
        "duracion_minutos": round((muestras[-1].momento - muestras[0].momento) / 60, 1),
        "pico_requests_por_segundo": round(pico_rps, 2),
        "pico_cpu_usada": round(pico_cpu, 3),
        "pico_memoria_mb": round(max(m.memoria_bytes for m in muestras) / 1e6, 1),
        # El total de 5xx es el ACUMULADO del proceso, no la suma de las muestras.
        "errores_5xx": max(m.requests_5xx for m in muestras),
        "reinicios_detectados": reinicios,
    }


def _scrapear(url: str, token: str, timeout: int = 20) -> str:
    pedido = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(pedido, timeout=timeout) as respuesta:  # noqa: S310
        return respuesta.read().decode("utf-8", errors="replace")


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2

    base = argv[1].rstrip("/")
    token = argv[2]
    cada = 15
    salida = f"metricas-{time.strftime('%Y%m%d-%H%M')}.jsonl"
    if "--cada" in argv:
        cada = int(argv[argv.index("--cada") + 1])
    if "--salida" in argv:
        salida = argv[argv.index("--salida") + 1]

    url = f"{base}/metrics"
    muestras: list[Muestra] = []
    print(f"Grabando {url} cada {cada}s en {salida}. Ctrl+C para cerrar y resumir.")

    try:
        with open(salida, "a", encoding="utf-8") as archivo:
            while True:
                try:
                    muestra = parsear_exposicion(_scrapear(url, token))
                    muestras.append(muestra)
                    fila = asdict(muestra)
                    if len(muestras) > 1:
                        fila.update(asdict(diferencia_entre(muestras[-2], muestra)))
                    archivo.write(json.dumps(fila) + "\n")
                    archivo.flush()  # que el archivo sirva aunque la máquina se apague
                    print(
                        f"  {time.strftime('%H:%M:%S')}  "
                        f"{fila.get('requests_por_segundo', 0):6.1f} req/s  "
                        f"{muestra.memoria_bytes / 1e6:6.1f} MB  "
                        f"5xx={muestra.requests_5xx}"
                    )
                except Exception as err:  # noqa: BLE001 — un scrape perdido no corta la grabación
                    print(f"  {time.strftime('%H:%M:%S')}  scrape falló: {err}")
                time.sleep(cada)
    except KeyboardInterrupt:
        pass

    resumen = resumir(muestras)
    print("\n=== RESUMEN ===")
    for clave, valor in resumen.items():
        print(f"  {clave}: {valor}")
    with open(salida, "a", encoding="utf-8") as archivo:
        archivo.write(json.dumps({"resumen": resumen}) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv))
