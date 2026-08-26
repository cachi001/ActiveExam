"""c-78 §16.3b — guardar `/metrics` durante el examen, para poder mirarlo después.

## Por qué esto existe

`/metrics` ya está protegido (16.3a) y expone lo que hace falta, pero **nadie lo
guarda**: Render free no corre un Prometheus al lado, así que la serie vive solo en la
memoria del proceso y se pierde en cada reinicio. Durante el examen eso significa que si
algo va mal, la única evidencia de qué pasó es lo que alguien haya alcanzado a mirar a
mano — y después del examen no queda nada que revisar.

Este grabador es la versión mínima que resuelve el problema sin infraestructura nueva:
scrapea cada N segundos desde cualquier máquina y deja un archivo por examen.

Los tests cubren la parte con lógica: leer el formato de exposición de Prometheus (que
son contadores acumulados, no tasas) y convertirlo en algo que se pueda leer después.
"""

from __future__ import annotations

import pytest

from app.observability.grabador_metricas import (
    Muestra,
    diferencia_entre,
    parsear_exposicion,
    resumir,
)

# Recorte real de lo que devuelve la app, con las series que importan.
EXPOSICION = """
# HELP http_requests_total Total de requests HTTP
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/api/v1/exam-content",status="200"} 1523.0
http_requests_total{method="POST",path="/api/v1/proctoring/events",status="201"} 8402.0
http_requests_total{method="POST",path="/api/v1/proctoring/events",status="500"} 3.0
# HELP http_request_duration_seconds Latencia
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_sum{method="POST",path="/api/v1/proctoring/events"} 4210.5
http_request_duration_seconds_count{method="POST",path="/api/v1/proctoring/events"} 8405.0
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes 167510016.0
# TYPE process_cpu_seconds_total counter
process_cpu_seconds_total 412.77
"""


class TestLeerLaExposicion:
    def test_suma_todos_los_requests(self) -> None:
        m = parsear_exposicion(EXPOSICION)

        assert m.requests_total == 1523 + 8402 + 3

    def test_separa_los_que_fallaron(self) -> None:
        """Los 5xx son la señal que importa durante un examen: un 500 en
        `/events` es evidencia que no se guardó."""
        m = parsear_exposicion(EXPOSICION)

        assert m.requests_5xx == 3

    def test_un_4xx_no_cuenta_como_falla_del_servidor(self) -> None:
        """Triangulación: 401 y 404 son ruido normal (tokens vencidos, rutas que
        no existen). Mezclarlos con los 5xx haría que el número deje de alarmar."""
        m = parsear_exposicion(
            EXPOSICION + '\nhttp_requests_total{method="GET",path="/x",status="404"} 12.0\n'
        )

        assert m.requests_5xx == 3
        assert m.requests_total == 1523 + 8402 + 3 + 12

    def test_lee_memoria_y_cpu(self) -> None:
        m = parsear_exposicion(EXPOSICION)

        assert m.memoria_bytes == pytest.approx(167510016.0)
        assert m.cpu_segundos == pytest.approx(412.77)

    def test_una_exposicion_vacia_no_revienta(self) -> None:
        """Si el scrape falla o vuelve cortado, el grabador tiene que seguir
        tomando muestras: perder una no puede terminar la grabación del examen."""
        m = parsear_exposicion("")

        assert m.requests_total == 0
        assert m.memoria_bytes == 0.0

    def test_ignora_comentarios_y_lineas_rotas(self) -> None:
        m = parsear_exposicion("# HELP algo\nesto_no_es_una_metrica\nhttp_requests_total{a=\"b\"} 5.0")

        assert m.requests_total == 5


class TestConvertirContadoresEnTasas:
    def test_calcula_los_requests_por_segundo_entre_dos_muestras(self) -> None:
        """Prometheus expone contadores ACUMULADOS. "1523 requests" no dice nada;
        lo que importa es cuántos por segundo, que es la diferencia entre dos
        muestras dividida por el tiempo que pasó."""
        antes = Muestra(momento=100.0, requests_total=1000, requests_5xx=0,
                        memoria_bytes=1.0, cpu_segundos=10.0)
        despues = Muestra(momento=110.0, requests_total=1200, requests_5xx=0,
                          memoria_bytes=1.0, cpu_segundos=15.0)

        delta = diferencia_entre(antes, despues)

        assert delta.requests_por_segundo == pytest.approx(20.0)

    def test_calcula_el_uso_de_cpu_como_fraccion(self) -> None:
        """5 segundos de CPU en 10 de reloj = 0,5 de un core. En Render free, que
        da 0,1, cualquier cosa cerca de eso es saturación."""
        antes = Muestra(momento=100.0, requests_total=0, requests_5xx=0,
                        memoria_bytes=1.0, cpu_segundos=10.0)
        despues = Muestra(momento=110.0, requests_total=0, requests_5xx=0,
                          memoria_bytes=1.0, cpu_segundos=15.0)

        delta = diferencia_entre(antes, despues)

        assert delta.cpu_usada == pytest.approx(0.5)

    def test_un_reinicio_del_proceso_no_produce_tasas_negativas(self) -> None:
        """Si Render reinicia el servicio, los contadores vuelven a cero. Sin esta
        guarda, el archivo del examen quedaría con -150 req/s en esa fila y el
        resumen final saldría mal."""
        antes = Muestra(momento=100.0, requests_total=5000, requests_5xx=2,
                        memoria_bytes=1.0, cpu_segundos=400.0)
        despues = Muestra(momento=110.0, requests_total=12, requests_5xx=0,
                          memoria_bytes=1.0, cpu_segundos=0.5)

        delta = diferencia_entre(antes, despues)

        assert delta.requests_por_segundo >= 0
        assert delta.reinicio_detectado is True

    def test_dos_muestras_del_mismo_instante_no_dividen_por_cero(self) -> None:
        igual = Muestra(momento=100.0, requests_total=10, requests_5xx=0,
                        memoria_bytes=1.0, cpu_segundos=1.0)

        delta = diferencia_entre(igual, igual)

        assert delta.requests_por_segundo == 0.0


class TestResumenFinal:
    def test_reporta_el_pico_y_los_errores(self) -> None:
        """Lo que uno quiere saber al terminar el examen: cuánto aguantó, cuánta
        memoria usó y si falló algo."""
        muestras = [
            Muestra(momento=0.0, requests_total=0, requests_5xx=0,
                    memoria_bytes=100e6, cpu_segundos=0.0),
            Muestra(momento=10.0, requests_total=150, requests_5xx=0,
                    memoria_bytes=180e6, cpu_segundos=5.0),
            Muestra(momento=20.0, requests_total=500, requests_5xx=4,
                    memoria_bytes=140e6, cpu_segundos=9.0),
        ]

        r = resumir(muestras)

        assert r["pico_requests_por_segundo"] == pytest.approx(35.0)
        assert r["pico_memoria_mb"] == pytest.approx(180.0, rel=1e-3)
        assert r["errores_5xx"] == 4
        assert r["muestras"] == 3

    def test_sin_muestras_devuelve_un_resumen_vacio_y_no_revienta(self) -> None:
        assert resumir([])["muestras"] == 0
