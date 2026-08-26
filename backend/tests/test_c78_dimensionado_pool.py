"""c-78 §16.2 — el pool de conexiones se dimensiona solo y avisa si no entra.

## El problema que esto cierra

`pool_size=12, max_overflow=12` estaba **fijo en el código**, con un comentario que
explicaba la cuenta para 4 workers (4 × 24 = 96 < 100). El número era correcto para ese
escenario y para ninguno más: cambiar el plan, subir workers o mover la base a un Postgres
con otro `max_connections` deja la cuenta vieja sin que nada lo diga. Ya pasó una vez —
30+30 por worker agotó Postgres bajo carga real y el 503 resultante escondía la causa.

Un límite que hay que recalcular a mano cuando cambia el entorno es un límite que
eventualmente queda mal. Acá se calcula desde los datos reales del entorno y, si no entra,
se dice antes de que Postgres empiece a rechazar conexiones en medio de un examen.
"""

from __future__ import annotations

import pytest

from app.infrastructure.persistence.session_activeexam import (
    MAX_OVERFLOW_DEFAULT,
    POOL_SIZE_DEFAULT,
    create_activeexam_engine,
)
from app.infrastructure.persistence.dimensionado_pool import (
    RESERVA_ADMIN,
    contar_workers,
    dimensionar_pool,
    verificar_pool_configurado,
)


# ---------------------------------------------------------------------------
# Cuánto pool le toca a cada worker
# ---------------------------------------------------------------------------


def test_un_solo_worker_se_queda_con_el_presupuesto_entero() -> None:
    """El caso de HOY: Render free, 0,1 de CPU, un proceso. Sin nadie con quien
    repartir, el worker puede usar todo lo que la base permita menos la reserva."""
    plan = dimensionar_pool(workers=1, max_connections=100)

    assert plan.total_por_worker() == 100 - RESERVA_ADMIN
    assert plan.techo_teorico() <= 100


def test_cuatro_workers_reparten_el_presupuesto_entre_ellos() -> None:
    """Triangulación: el que rompió producción. Cada worker es un PROCESO con su
    propio engine y su propio pool, así que el techo real es workers × pool."""
    plan = dimensionar_pool(workers=4, max_connections=100)

    assert plan.techo_teorico() <= 100 - RESERVA_ADMIN
    assert plan.total_por_worker() == (100 - RESERVA_ADMIN) // 4


def test_una_base_mas_grande_habilita_mas_conexiones_por_worker() -> None:
    """El pool sale del `max_connections` REAL, no de un número escrito a mano: la
    misma app contra un Postgres más grande tiene que poder usarlo."""
    chico = dimensionar_pool(workers=4, max_connections=100)
    grande = dimensionar_pool(workers=4, max_connections=500)

    assert grande.total_por_worker() > chico.total_por_worker()
    assert grande.techo_teorico() <= 500 - RESERVA_ADMIN


def test_nunca_baja_del_minimo_util() -> None:
    """Con muchos workers sobre una base chica, la división da un pool ridículo. Un
    pool de 1 serializa TODO el tráfico de ese worker: es peor que el problema que
    se quería evitar, y encima silencioso. Se piso en un mínimo usable."""
    plan = dimensionar_pool(workers=32, max_connections=50)

    assert plan.total_por_worker() >= 4


def test_el_pool_se_reparte_mitad_fijo_mitad_overflow() -> None:
    """`pool_size` son conexiones que quedan abiertas; `max_overflow`, las que se
    abren solo bajo pico y se descartan. Mitad y mitad conserva el criterio que ya
    tenía el código (12+12), ahora derivado en vez de escrito."""
    plan = dimensionar_pool(workers=1, max_connections=100)

    assert plan.pool_size + plan.max_overflow == plan.total_por_worker()
    assert abs(plan.pool_size - plan.max_overflow) <= 1


# ---------------------------------------------------------------------------
# La guarda: avisar cuando lo configurado NO entra
# ---------------------------------------------------------------------------


def test_una_configuracion_que_entra_no_tiene_nada_que_decir() -> None:
    problema = verificar_pool_configurado(
        workers=1, pool_size=12, max_overflow=12, max_connections=100
    )

    assert problema is None


def test_avisa_cuando_los_workers_por_su_pool_superan_la_base() -> None:
    """El caso real de producción: 4 workers × 60 = 240 contra max_connections=100.
    Postgres empezó a rechazar y el 503 no decía por qué."""
    problema = verificar_pool_configurado(
        workers=4, pool_size=30, max_overflow=30, max_connections=100
    )

    assert problema is not None
    # El mensaje tiene que traer los números que hacen falta para arreglarlo, no un
    # "configuración inválida" que obliga a ir a leer el código.
    assert "240" in problema
    assert "100" in problema


def test_el_aviso_tambien_salta_al_comerse_la_reserva_de_admin() -> None:
    """Triangulación del borde: 96 < 100 entra "por poco", pero deja a Postgres sin
    conexiones libres para que un administrador entre a ver qué pasa — que es
    justamente lo que uno necesita cuando esto se rompe."""
    problema = verificar_pool_configurado(
        workers=4, pool_size=12, max_overflow=12, max_connections=100
    )

    assert problema is not None
    assert str(RESERVA_ADMIN) in problema


@pytest.mark.parametrize("workers", [0, -1])
def test_workers_invalidos_no_producen_una_division_por_cero(workers: int) -> None:
    """`WEB_CONCURRENCY=0` mal seteada no puede tumbar el arranque con un
    ZeroDivisionError: se trata como un worker."""
    plan = dimensionar_pool(workers=workers, max_connections=100)

    assert plan.total_por_worker() > 0


# ---------------------------------------------------------------------------
# Contar los workers: la variable de entorno NO alcanza
# ---------------------------------------------------------------------------


def test_los_workers_se_leen_de_la_variable_cuando_esta(monkeypatch) -> None:
    monkeypatch.setenv("WEB_CONCURRENCY", "4")

    assert contar_workers() == 4


def test_sin_variable_se_cuentan_los_procesos_hermanos(monkeypatch) -> None:
    """El caso que se escapó: `uvicorn --workers 4` levanta 4 procesos SIN setear
    ninguna variable, así que leer el entorno reportaba 1 worker y la guarda daba
    "todo bien" con 96 conexiones posibles contra 90 disponibles.

    Los workers de uvicorn son hijos del mismo proceso padre: contarlos es mirar
    cuántos hermanos comparten el ppid."""
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)

    assert contar_workers(hermanos=lambda: 4) == 4


def test_sin_variable_y_sin_poder_contar_asume_uno(monkeypatch) -> None:
    """Fuera de Linux no hay /proc que leer. Asumir 1 es lo único honesto; el aviso
    de conexiones reales (que no depende de esto) sigue cubriendo el caso."""
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)

    assert contar_workers(hermanos=lambda: None) == 1


def test_la_variable_le_gana_al_conteo_de_procesos(monkeypatch) -> None:
    """Si alguien declaró WEB_CONCURRENCY, esa es la intención explícita del
    despliegue y manda sobre lo que se pueda inferir mirando el sistema."""
    monkeypatch.setenv("WEB_CONCURRENCY", "2")

    assert contar_workers(hermanos=lambda: 8) == 2


def test_el_caso_real_de_dev_queda_marcado_como_problema() -> None:
    """La configuración que estaba corriendo mientras se escribió esto:
    `uvicorn --workers 4` con pool 12+12 contra max_connections=100. 4 x 24 = 96,
    y quedan 90 después de la reserva. Entra "por poco" en el límite duro y se come
    entera la reserva de administración."""
    problema = verificar_pool_configurado(
        workers=4, pool_size=12, max_overflow=12, max_connections=100
    )

    assert problema is not None
    assert "96" in problema


# ---------------------------------------------------------------------------
# El pool se puede configurar sin tocar el código
# ---------------------------------------------------------------------------


def test_el_pool_sale_del_entorno_cuando_esta_seteado(monkeypatch) -> None:
    """Arreglar un pool mal dimensionado no puede exigir editar el código y
    reconstruir la imagen: en medio de un examen eso no es una opción."""
    monkeypatch.setenv("DB_POOL_SIZE", "9")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "9")

    eng = create_activeexam_engine("postgresql+asyncpg://u:p@localhost:5432/x")

    assert eng.pool.size() == 9
    assert eng.pool._max_overflow == 9  # noqa: SLF001


def test_sin_entorno_usa_los_valores_por_defecto(monkeypatch) -> None:
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)

    eng = create_activeexam_engine("postgresql+asyncpg://u:p@localhost:5432/x")

    assert eng.pool.size() == POOL_SIZE_DEFAULT
    assert eng.pool._max_overflow == MAX_OVERFLOW_DEFAULT  # noqa: SLF001


@pytest.mark.parametrize("basura", ["", "  ", "cuatro", "0", "-3"])
def test_una_variable_mal_escrita_no_tumba_el_arranque(monkeypatch, basura: str) -> None:
    """Un `DB_POOL_SIZE=cuatro` tiene que degradar al default, no reventar el
    arranque de la app entera."""
    monkeypatch.setenv("DB_POOL_SIZE", basura)

    eng = create_activeexam_engine("postgresql+asyncpg://u:p@localhost:5432/x")

    assert eng.pool.size() == POOL_SIZE_DEFAULT
