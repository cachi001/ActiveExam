/**
 * Envio con respaldo y reintento de drenaje (c-78).
 *
 * ## Por que existe
 *
 * El patron "guardar en el buffer ANTES de mandar, purgar recien cuando el
 * backend contesta" estaba escrito a mano adentro de `useExamProctoring`, en el
 * camino de los eventos discretos. La captura de pausa, que es otro camino de
 * envio del mismo hook, no lo tenia: salia fire-and-forget y se perdia con la
 * conexion. Extraerlo deja UNA implementacion para los dos.
 *
 * ## Que resuelve el reintento
 *
 * El drenaje colgaba unicamente de `window.addEventListener('online')`. Eso deja
 * afuera dos casos que en un examen real son la norma, no la excepcion:
 *
 *  - La conexion vuelve sin que el navegador dispare `online` (el adaptador de
 *    red nunca se cayo: se cayo el enlace, el wifi del edificio, el server).
 *  - **El alumno recarga la pagina.** Si el corte ya paso, `online` no va a
 *    dispararse nunca mas, y lo que quedo bufferizado de la sesion anterior no
 *    se reenvia jamas.
 *
 * Por eso el reintento drena una vez al arrancar y despues periodicamente, sin
 * depender de ningun evento del navegador.
 */

import type { CircularEventBuffer } from "./eventBuffer";

/**
 * Cada cuanto se reintenta el drenaje. 30 s: lo suficientemente seguido para que
 * la evidencia llegue mientras el examen sigue vivo, y lo suficientemente
 * espaciado para no castigar al backend con replays encimados durante un corte
 * (con el buffer vacio el reintento no hace ningun pedido de red).
 */
export const INTERVALO_REINTENTO_DRENAJE_MS = 30_000;

export interface ResultadoEnvio {
  /** true si el backend confirmo; false si quedo esperando en el buffer. */
  enviado: boolean;
}

/**
 * Manda un payload dejandolo respaldado en el buffer hasta que el backend lo
 * confirme.
 *
 * 1. Persiste ANTES del POST (idempotente por `id`: re-bufferizar no duplica).
 * 2. Ejecuta el POST.
 * 3. Si resuelve OK -> `confirm(id)` para PURGAR del buffer.
 * 4. Si rechaza -> NO confirma: queda pendiente para el drenaje.
 *
 * El paso 3 no es un detalle: sin la purga en exito, el buffer retiene todos los
 * eventos del examen y el primer drenaje se los reinyecta de golpe al backend,
 * que no deduplica.
 *
 * NUNCA lanza. Un problema de red o de almacenamiento no puede tumbar el examen
 * del alumno; el que se entera es el llamador, por el valor de retorno.
 */
export async function enviarConRespaldo<T extends object>(
  buffer: CircularEventBuffer | null,
  id: string,
  payload: T,
  enviar: (payload: T) => Promise<unknown>,
): Promise<ResultadoEnvio> {
  await buffer?.append(id, payload).catch(() => {});

  try {
    await enviar(payload);
  } catch (err) {
    console.error("[proctoring] POST falló, queda en el buffer para reenvío:", err);
    return { enviado: false };
  }

  await buffer?.confirm(id).catch(() => {});
  return { enviado: true };
}

export interface EnvioReintentableDeps<T> {
  /** Manda el valor. Si rechaza, el valor queda pendiente. */
  enviar: (valor: T) => Promise<unknown>;
}

/**
 * Envío de UN valor que no se suelta hasta que el backend lo confirmó.
 *
 * Existe por un bug concreto: el payload biométrico (la verificación de identidad
 * del alumno) se mandaba fire-and-forget y el llamador lo borraba del store en la
 * misma línea, sin esperar el resultado. Un hipo de red al arrancar el examen
 * —justo el momento en que entran todos a la vez— y esa verificación se perdía
 * para siempre, sin que nadie se enterara.
 *
 * A diferencia del buffer de eventos, esto NO persiste en disco a propósito: el
 * payload biométrico es dato sensible (Ley 25.326) y no se escribe fuera de la
 * memoria de la sesión. El reintento vive lo que vive la pestaña.
 */
export function crearEnvioReintentable<T>(deps: EnvioReintentableDeps<T>) {
  let pendiente: { valor: T } | null = null;

  const intentar = async (valor: T): Promise<boolean> => {
    try {
      await deps.enviar(valor);
    } catch (err) {
      console.error("[proctoring] envío falló, queda pendiente de reintento:", err);
      pendiente = { valor };
      return false;
    }
    pendiente = null;
    return true;
  };

  return {
    /** Manda ahora. Devuelve si llegó; si no, queda pendiente. Nunca lanza. */
    enviar: (valor: T): Promise<boolean> => intentar(valor),
    /** Reintenta lo que haya quedado. Sin pendiente no toca la red. */
    async reintentar(): Promise<void> {
      if (pendiente === null) return;
      await intentar(pendiente.valor);
    },
    hayPendiente: (): boolean => pendiente !== null,
  };
}

export interface ReintentoDeDrenajeDeps {
  /** Drena el buffer contra el backend. Puede rechazar: se reintenta igual. */
  drenar: () => Promise<void>;
  intervalMs?: number;
}

/**
 * Controlador de reintento del drenaje, PURO respecto del DOM (recibe su
 * dependencia por parametro), en el mismo espiritu que
 * `crearControladorCapturaPausa`.
 *
 * Drena una vez al arrancar —para lo que haya quedado de una sesion anterior— y
 * despues cada `intervalMs`. No encima drenajes: si el anterior sigue en vuelo
 * (tipico con la red caida, esperando timeouts), el tick se saltea.
 */
export function crearReintentoDeDrenaje(deps: ReintentoDeDrenajeDeps) {
  const intervalMs = deps.intervalMs ?? INTERVALO_REINTENTO_DRENAJE_MS;
  let timer: ReturnType<typeof setInterval> | null = null;
  let enVuelo = false;

  const intentar = async (): Promise<void> => {
    if (enVuelo) return;
    enVuelo = true;
    try {
      await deps.drenar();
    } catch {
      // Sigue sin haber red: el proximo tick reintenta. No hay nada que loguear
      // por cada intento fallido — seria ruido durante todo el corte.
    } finally {
      enVuelo = false;
    }
  };

  return {
    arrancar(): void {
      if (timer !== null) return;
      void intentar();
      timer = setInterval(() => void intentar(), intervalMs);
    },
    detener(): void {
      if (timer !== null) {
        clearInterval(timer);
        timer = null;
      }
    },
    /** Fuerza un intento ya (lo usa el listener de `online`). */
    ahora(): void {
      void intentar();
    },
  };
}
