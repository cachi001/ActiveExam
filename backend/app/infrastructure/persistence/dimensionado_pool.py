"""Cuántas conexiones puede abrir cada worker sin agotar Postgres (c-78 §16.2).

El pool estaba fijo en `pool_size=12, max_overflow=12`, con la cuenta para 4 workers
escrita en un comentario: 4 × 24 = 96 < 100. Correcta para ese escenario y para ninguno
otro. Cambiar el plan, subir `WEB_CONCURRENCY` o mover la base a otro Postgres deja la
cuenta vieja sin que nada lo diga, y el modo en que eso se manifiesta es el peor posible:
Postgres rechaza conexiones bajo carga y la app responde 503 sin explicar por qué. Ya pasó
con 30+30 por worker (4 × 60 = 240 contra `max_connections=100`).

Acá el número se deriva de los datos reales del entorno — cuántos workers hay y cuánto
permite la base — y la guarda avisa antes de arrancar si lo configurado no entra.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

# Conexiones que se dejan libres SIEMPRE, fuera del reparto entre workers. Son las
# que necesita un administrador para entrar a mirar qué pasa, y las que usan las
# tareas de mantenimiento (migraciones, backups). Quedarse sin ellas justo cuando la
# app agotó el resto deja el problema sin diagnóstico posible.
RESERVA_ADMIN = 10

# Piso por worker. Por debajo de esto el pool serializa el trabajo del proceso y la
# latencia se dispara sin que ninguna métrica de CPU lo muestre.
MINIMO_POR_WORKER = 4


@dataclass(frozen=True)
class PlanDePool:
    """Cuántas conexiones abre cada worker: fijas (`pool_size`) y de pico
    (`max_overflow`)."""

    pool_size: int
    max_overflow: int
    workers: int

    def total_por_worker(self) -> int:
        """Máximo de conexiones simultáneas de UN worker."""
        return self.pool_size + self.max_overflow

    def techo_teorico(self) -> int:
        """Máximo de conexiones de TODA la app: cada worker es un proceso con su
        propio engine y su propio pool."""
        return self.total_por_worker() * self.workers


def _hermanos_del_mismo_padre() -> int | None:
    """Cuántos procesos comparten padre con este, leyendo `/proc`.

    Los workers de uvicorn son hijos de un mismo proceso supervisor, así que
    contarlos es contar hermanos. Devuelve `None` donde no hay `/proc` (Windows,
    macOS): ahí no se puede saber y no se inventa.
    """
    try:
        mi_padre = os.getppid()
        hermanos = 0
        for entrada in os.listdir("/proc"):
            if not entrada.isdigit():
                continue
            try:
                with open(f"/proc/{entrada}/stat", encoding="utf-8") as f:
                    campos = f.read().rsplit(")", 1)[-1].split()
                # Tras el ")" del nombre: estado, luego ppid.
                if len(campos) >= 2 and int(campos[1]) == mi_padre:
                    hermanos += 1
            except (OSError, ValueError):
                continue  # el proceso murió mientras lo leíamos
        return hermanos or None
    except OSError:
        return None


def contar_workers(hermanos: Callable[[], int | None] | None = None) -> int:
    """Cuántos procesos de la app pueden abrir un pool, para calcular el techo real.

    `WEB_CONCURRENCY` manda cuando está: es la intención explícita del despliegue.
    Pero `uvicorn --workers 4` levanta cuatro procesos SIN setear ninguna variable —
    así arranca hoy el entorno de desarrollo— y ahí leer el entorno reporta 1 y la
    cuenta sale mal por un factor de cuatro. Por eso, sin variable, se cuentan los
    procesos de verdad.

    Cuenta PROCESOS, que puede ser uno más que los workers declarados: el supervisor
    de uvicorn tiene un hijo extra además de los N workers. Para un techo de
    conexiones eso es lo correcto — es un límite superior, y errar hacia arriba avisa
    de más, nunca de menos.
    """
    declarado = os.getenv("WEB_CONCURRENCY", "").strip()
    if declarado:
        try:
            return _workers_validos(int(declarado))
        except ValueError:
            pass  # basura en la variable: se cuenta a mano, abajo

    contar = hermanos or _hermanos_del_mismo_padre
    return _workers_validos(contar() or 1)


def _workers_validos(workers: int) -> int:
    # `WEB_CONCURRENCY=0` mal seteada no puede tumbar el arranque con un
    # ZeroDivisionError. Sin workers declarados hay, como mínimo, el proceso actual.
    return max(1, workers)


def dimensionar_pool(workers: int, max_connections: int) -> PlanDePool:
    """Reparte el presupuesto de conexiones de la base entre los workers.

    El presupuesto es `max_connections` menos la reserva de administración. Se divide
    en partes iguales y cada parte se abre mitad fija, mitad de pico — el mismo
    criterio que tenía el 12+12 escrito a mano, ahora derivado.
    """
    workers = _workers_validos(workers)
    presupuesto = max(max_connections - RESERVA_ADMIN, MINIMO_POR_WORKER)
    por_worker = max(presupuesto // workers, MINIMO_POR_WORKER)

    pool_size = por_worker // 2
    max_overflow = por_worker - pool_size
    return PlanDePool(pool_size=pool_size, max_overflow=max_overflow, workers=workers)


def verificar_pool_configurado(
    workers: int, pool_size: int, max_overflow: int, max_connections: int
) -> str | None:
    """`None` si la configuración entra en la base; si no, el motivo, con los números.

    El mensaje trae el techo, el límite y la reserva a propósito: quien lo lee está
    mirando un arranque que falla o un examen que se cae, y "configuración inválida"
    lo obligaría a ir a leer este archivo para saber qué tocar.
    """
    workers = _workers_validos(workers)
    techo = (pool_size + max_overflow) * workers
    disponible = max_connections - RESERVA_ADMIN

    if techo <= disponible:
        return None

    return (
        f"El pool configurado puede abrir hasta {techo} conexiones "
        f"({workers} proceso(s) x {pool_size + max_overflow}), pero la base admite "
        f"{max_connections} y se reservan {RESERVA_ADMIN} para administración: "
        f"quedan {disponible}. Bajo carga, Postgres va a empezar a rechazar "
        f"conexiones y la app va a responder 503 sin decir por qué."
    )
