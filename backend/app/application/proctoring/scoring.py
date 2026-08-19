"""Calculo de score de riesgo para sesiones de proctoring activeexam.

Motor SIMPLE: suma directa de pesos por tipo de evento. Lo usa el endpoint del
detalle de sesion (vista del proctor) — devuelve el score on-the-fly sin
persistir. L2.5: el score solo PRIORIZA la cola de revision humana — el backend
NUNCA sanciona ni emite veredicto disciplinario.

COEXISTENCIA INTENCIONAL con ``app.domain.scoring.risk_score`` (motor del cierre,
``score_correlacionado``): ambos leen de la MISMA fuente de pesos
(``evento_score_config`` via ConfigService.scoring_weights). La diferencia es la
forma de combinar: el motor de cierre suma + correlacion + bono por persistencia
(el "score final" persistido); este suma directa (el "score on-the-fly" del
proctor). Coinciden en el peso base; difieren en bonos.

Fallback por severidad: red de seguridad si la config no esta disponible. Las
severidades canonicas (alineadas con ``evento_score_config`` y el dominio) son
``baja``, ``media``, ``alta``, ``critica`` — la severidad ``baseline`` NO suma
(es el piso 0 del score, no un evento). Los pesos de fallback estan en el centro
de los rangos institucionales por severidad (``SEVERITY_RANGES``).
"""

from __future__ import annotations

from datetime import datetime

from app.domain.events.schema import Severidad

# Fallback por severidad (RN-GLB-03 — solo si la config persistida no esta). Los
# valores son el centro del rango institucional definido en
# ``app/domain/scoring/risk_score.SEVERITY_RANGES``:
#   baja    [1-10]   -> 5
#   media   [11-30]  -> 20
#   alta    [31-60]  -> 45
#   critica [61-100] -> 80
# baseline no es un evento (no suma al score).
#
# Las claves salen del ENUM, no de literales: una tabla de pesos escrita a mano se
# desincroniza del vocabulario sin que nada falle (un ``.get`` que no matchea
# devuelve 0 y el score se cae en silencio). Indexar por ``Severidad`` hace que un
# valor inventado reviente al importar el modulo, no en produccion.
PESOS_SEVERIDAD: dict[str, int] = {
    Severidad.BAJA.value: 5,
    Severidad.MEDIA.value: 20,
    Severidad.ALTA.value: 45,
    Severidad.CRITICA.value: 80,
}

# Tope del score (igual que el cliente y la finalizacion de produccion). El score
# es 0..100; nunca se persiste ni se muestra por encima de 100.
SCORE_CAP = 100

# Umbral de riesgo "medio" (C-76 tarea 17). Espeja SCORE_UMBRAL_MEDIO del cliente
# (frontend/src/screens/proctoring/helpers.ts) — NO configurable ahi tampoco, asi
# que no hay una fuente persistida que leer (a diferencia del umbral "alto", que
# SI es configurable via configuracion_sistema.umbral_cola_revision).
SCORE_UMBRAL_MEDIO = 30


def nivel_riesgo(score: int, umbral_alto: int) -> str:
    """Nivel de riesgo derivado del score: 'bajo' | 'medio' | 'alto'.

    Espeja EXACTAMENTE `nivelRiesgo()` del frontend (proctoring/helpers.ts):
    ``score >= umbral_alto`` -> alto; ``score >= SCORE_UMBRAL_MEDIO`` -> medio;
    si no, bajo. ``umbral_alto`` es el umbral de cola de revision VIVO
    (``ConfiguracionSistemaModel.umbral_cola_revision`` via ConfigService), NO
    una constante hardcodeada — el mismo umbral que ya usa la Cola de revision.
    """
    if score >= umbral_alto:
        return "alto"
    if score >= SCORE_UMBRAL_MEDIO:
        return "medio"
    return "bajo"


def calcular_score(
    eventos: list,
    pesos_por_tipo: dict[str, int] | None = None,
    tipos_desactivados: frozenset[str] | set[str] | None = None,
) -> int:
    """Calcula el score de riesgo de una sesion sumando pesos por evento.

    Si ``pesos_por_tipo`` esta presente (pesos VIVOS de la config persistida,
    ``evento_score_config`` via ConfigService), cada evento aporta el peso de su
    ``tipo``; si el tipo no esta en el mapa vivo, cae al peso por severidad como red
    de seguridad de degradacion (RN-GLB-03). Sin ``pesos_por_tipo`` (config ausente)
    usa SOLO la red de seguridad por severidad — nunca como fuente normal.

    Args:
        eventos: Lista de objetos duck-typed con ``severidad`` (y opcionalmente
            ``tipo``). Acepta ProctoringEventModel.
        pesos_por_tipo: Mapa ``{tipo_evento: peso}`` de los tipos ACTIVOS en la
            config. None = sin config (fallback por severidad).
        tipos_desactivados: Tipos con fila en ``evento_score_config`` pero
            ``activo=False``. Pesan 0 — el admin los apago a proposito. Es
            distinto de "tipo ausente de la config" (desconocido), que SI degrada
            por severidad: sin esta distincion, apagar un detector y estrenar uno
            nuevo se comportaban igual.

    Returns:
        Score entero >= 0. Score 0 si no hay eventos o el peso no se resuelve.

    Note:
        L2.5: el score SOLO prioriza la revision humana. El backend nunca sanciona.
    """
    pesos = pesos_por_tipo or {}
    desactivados = tipos_desactivados or frozenset()
    total = 0
    for e in eventos:
        tipo = getattr(e, "tipo", "")
        if tipo and tipo in desactivados:
            # Tipo APAGADO por el admin: pesa 0, no cae al fallback. Sin esto,
            # desactivarlo lo dejaba sumando igual server-side mientras el cliente
            # lo trataba como 0 — dos scores distintos para la misma sesion.
            continue
        if tipo and tipo in pesos:
            total += pesos[tipo]
        else:
            # Tipo DESCONOCIDO para la config (sin fila en evento_score_config) o
            # config no disponible: red de seguridad por severidad (RN-GLB-03). Un
            # detector nuevo no puede quedar valiendo 0 en silencio.
            total += PESOS_SEVERIDAD.get(getattr(e, "severidad", ""), 0)
    # Cap a 100: el score es 0..100 (coincide con el cliente y la finalizacion).
    return min(SCORE_CAP, total)


# ---------------------------------------------------------------------------
# Snapshot de config al crear la sesion (migration 0083).
#
# Un cambio de config del sistema (umbral, pesos de scoring) NO debe afectar
# retroactivamente a una sesion que ya arranco (regla de producto, ver
# migrations/versions/0083_config_snapshot_proctoring_session.py). Estas
# funciones construyen la foto al CREAR la sesion y la leen de vuelta al
# puntuar: si la sesion tiene snapshot, manda; si no (sesion pre-migracion o
# config no disponible al crear), se cae a la config VIVA (comportamiento
# previo a este change).
# ---------------------------------------------------------------------------


def construir_config_snapshot(
    *,
    umbral_cola_revision: int,
    pesos_por_tipo: dict[str, int] | None,
    tipos_desactivados: frozenset[str] | set[str] | None,
) -> dict:
    """Arma el dict JSON-safe que se persiste en ``proctoring_session.config_snapshot``."""
    return {
        "umbral_cola_revision": umbral_cola_revision,
        "scoring_weights": dict(pesos_por_tipo or {}),
        "scoring_desactivados": sorted(tipos_desactivados or ()),
    }


def pesos_de_snapshot(
    config_snapshot: dict | None, *, pesos_vivos: dict[str, int] | None
) -> dict[str, int] | None:
    """Pesos por tipo: los de la foto si la sesion tiene una; si no, los vivos."""
    if config_snapshot:
        return dict(config_snapshot.get("scoring_weights") or {})
    return pesos_vivos


def desactivados_de_snapshot(
    config_snapshot: dict | None, *, desactivados_vivos: frozenset[str] | set[str] | None
) -> frozenset[str]:
    """Tipos desactivados: los de la foto si la sesion tiene una; si no, los vivos."""
    if config_snapshot:
        return frozenset(config_snapshot.get("scoring_desactivados") or ())
    return frozenset(desactivados_vivos or ())


def umbral_de_snapshot(config_snapshot: dict | None, *, umbral_vivo: int) -> int:
    """Umbral de cola de revision: el de la foto si la sesion tiene una; si no, el vivo."""
    if config_snapshot:
        val = config_snapshot.get("umbral_cola_revision")
        if val is not None:
            return int(val)
    return umbral_vivo


def _en_ventana(
    ts: datetime | None, inicio: datetime | None, fin: datetime | None, ahora: datetime
) -> bool:
    """True si ``ts`` cae dentro de la ventana [inicio, fin or ahora] (bordes inclusive).

    Una pausa aprobada todavia activa (``fin is None``) usa ``ahora`` como cierre
    de la ventana. Si no hay ``inicio`` la ventana no esta definida y no contiene
    nada (la pausa no abrio ventana: rechazada o sin aprobar)."""
    if ts is None or inicio is None:
        return False
    cierre = fin if fin is not None else ahora
    return inicio <= ts <= cierre


def eventos_en_pausa_autorizada(
    eventos: list, ventanas: list, ahora: datetime | None = None
) -> set[str]:
    """Devuelve el set de ids de eventos cuyo ``ts_backend`` cae en alguna ventana de pausa.

    HELPER PURO (sin DB, sin red) — testeable en aislamiento. Implementa la
    contextualizacion del score (Opcion 1, sabor 1a): los eventos producidos
    DURANTE una pausa autorizada se EXCLUYEN del puntaje (no se borran ni se
    ocultan; L2.5 regla #6).

    Args:
        eventos: objetos duck-typed con ``id`` y ``ts_backend`` (datetime).
        ventanas: objetos duck-typed con ``estado``, ``inicio_en``, ``fin_en``. Solo
            cuentan las ventanas de pausa APROBADA — estados ``aprobada`` y
            ``finalizada``. ``solicitada``/``rechazada`` no abren ventana.
        ahora: cierre para ventanas activas (``fin_en is None``). Default: ``datetime.now``
            con tz de ``inicio_en`` si la hay, si no naive ``utcnow``-equivalente.

    Returns:
        Set de ``id`` (str) de los eventos que caen dentro de alguna ventana aprobada.
    """
    ventanas_aprobadas = [
        v for v in ventanas if getattr(v, "estado", "") in ("aprobada", "finalizada")
    ]
    if not ventanas_aprobadas:
        return set()

    ids: set[str] = set()
    for e in eventos:
        ts = getattr(e, "ts_backend", None)
        if ts is None:
            continue
        # ``ahora`` debe ser comparable con ``ts`` (aware vs naive). Lo derivamos
        # del propio ts para evitar TypeError al comparar datetimes con/sin tz.
        ref_ahora = ahora if ahora is not None else datetime.now(tz=getattr(ts, "tzinfo", None))
        for v in ventanas_aprobadas:
            if _en_ventana(
                ts,
                getattr(v, "inicio_en", None),
                getattr(v, "fin_en", None),
                ref_ahora,
            ):
                ids.add(getattr(e, "id"))
                break
    return ids
