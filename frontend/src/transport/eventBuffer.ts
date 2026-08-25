/**
 * Buffer circular de eventos del estudiante (C-14, RN-HB-02, Flujo 5, D1).
 *
 * Persiste cada evento ANTES de enviarlo; si el WS cae, los eventos siguen
 * guardandose sin perdida. El buffer es CIRCULAR (acotado): en cortes largos no
 * crece sin techo (descarta el mas viejo). Sobrevive a refresh/cierre de pestaña
 * porque el almacenamiento real es IndexedDB.
 *
 * El almacenamiento esta detras de un PUERTO (``EventBufferStore``): el adaptador
 * IndexedDB es de produccion; el adaptador en memoria es para tests. La logica de
 * orden, deduplicacion y circularidad vive aca, desacoplada del DOM.
 *
 * ## c-78: el buffer carga CAPTURAS, no solo eventos livianos
 *
 * El screenshot de un incidente viaja DENTRO del payload del evento (~114 KB en
 * base64: 960x540, JPEG 0.7). El diseño original, pensado para mensajes de unos
 * pocos KB, no aguantaba eso por tres motivos, corregidos aca:
 *
 *  1. **El techo era la cantidad** (10.000 registros). Con capturas adentro eso
 *     son 1,1 GB: mas de lo que ningun navegador concede. Ahora el techo que
 *     manda es el PESO (``maxBytes``), y la cantidad queda de guarda secundaria.
 *  2. **``append`` leia el buffer entero en cada evento** para deduplicar y para
 *     encontrar al mas viejo. Con capturas, guardar el evento 50 significaba
 *     parsear 5,7 MB de base64 en el hilo principal, encima del examen del
 *     alumno. Ahora el peso total y el ``seq`` se calculan UNA vez al arrancar
 *     (``resumen()``) y se mantienen incrementales.
 *  3. **``nextSeq`` arrancaba de cero en cada instancia.** Si el alumno recargaba
 *     la pagina con eventos sin enviar, los nuevos se numeraban ENCIMA de los
 *     bufferizados y el replay los reenviaba desordenados.
 *
 * Nada se descarta en silencio: expulsar por presupuesto o que el navegador
 * niegue el guardado avisa por ``alAvisar``, para que la pantalla del examen
 * pueda decirselo al alumno (misma logica que el aviso de "no se estan guardando
 * tus respuestas").
 */

/** Evento bufferizado: el contrato firmado de C-10 + un seq local monotono. */
export interface BufferedEvent {
  /** ``event_id`` del contrato (clave de deduplicacion, RN-HB-03). */
  id: string;
  /** Mensaje serializado tal cual se enviara por el WS (firmado). */
  message: object;
  /** Secuencia local monotona; fija el ORDEN de produccion (replay ordenado). */
  seq: number;
  /**
   * Peso aproximado del mensaje en bytes, para el presupuesto del buffer.
   * Opcional: los registros escritos por versiones anteriores no lo tienen y se
   * cuentan como 0 (el presupuesto se corrige solo al rotar).
   */
  bytes?: number;
}

/**
 * Puerto de almacenamiento del buffer. El adaptador concreto (IndexedDB o memoria)
 * solo persiste/lee/borra; el orden y la circularidad los gobierna el buffer.
 */
export interface EventBufferStore {
  put(record: BufferedEvent): Promise<void>;
  /** Un registro por ``id``, o null si no esta. */
  get(id: string): Promise<BufferedEvent | null>;
  /** Todos los registros, en orden ascendente de ``seq``. */
  getAllOrdered(): Promise<BufferedEvent[]>;
  /** Borra por ``id`` (confirmacion/purga). */
  delete(id: string): Promise<void>;
  /** Cantidad actual de registros. */
  count(): Promise<number>;
  /** El registro mas viejo (menor ``seq``), o null si vacio. */
  oldest(): Promise<BufferedEvent | null>;
  /**
   * Estado agregado del store, para arrancar sin recorrerlo en cada append:
   * peso total en bytes y mayor ``seq`` guardado (-1 si esta vacio).
   */
  resumen(): Promise<{ bytes: number; maxSeq: number }>;
}

export const DEFAULT_BUFFER_CAPACITY = 10_000;

/**
 * Presupuesto de disco del buffer. 200 MB son ~1.750 capturas de 114 KB.
 *
 * El calibre viene del peor caso REAL medido sobre el motor de reglas: cada regla
 * re-emite como mucho una vez por episodio (``face_absent_ms`` = 3 s), asi que un
 * alumno tapandose y destapandose la cara sin parar genera ~1.200 capturas por
 * hora (~137 MB). Un examen normal genera unos pocos incidentes: menos de 1 MB.
 * Chrome le concede a IndexedDB hasta el 60% del disco libre, con lo cual 200 MB
 * no es un numero agresivo — esta puesto para que el buffer NO se llene y no haya
 * que elegir que evidencia se tira.
 */
export const DEFAULT_BUFFER_MAX_BYTES = 200 * 1024 * 1024;

/** Por que el buffer no pudo guardar algo tal cual se le pidio. */
export type MotivoAviso =
  /** El navegador nego el guardado (cuota agotada): el evento NO quedo. */
  | "sin-espacio"
  /** Se expulso un registro viejo para hacerle lugar al nuevo. */
  | "expulsado";

export interface CircularBufferOptions {
  /** Presupuesto en bytes (default ``DEFAULT_BUFFER_MAX_BYTES``). */
  maxBytes?: number;
  /** Se llama cuando hubo que resignar algo. Nunca se descarta en silencio. */
  alAvisar?: (motivo: MotivoAviso, detalle?: unknown) => void;
}

/** Peso aproximado del mensaje. Sirve para presupuestar, no para facturar. */
export function pesoAproximado(message: object): number {
  try {
    return JSON.stringify(message)?.length ?? 0;
  } catch {
    return 0; // no serializable: no lo contamos, el store dira si entra
  }
}

export class CircularEventBuffer {
  private nextSeq = 0;
  private bytesUsados = 0;
  private arranque: Promise<void> | null = null;
  /** Peso por id de lo bufferizado en ESTA sesion, para no releer al confirmar. */
  private readonly pesos = new Map<string, number>();
  private readonly maxBytes: number;
  private readonly alAvisar: (motivo: MotivoAviso, detalle?: unknown) => void;

  constructor(
    private readonly store: EventBufferStore,
    private readonly capacity: number = DEFAULT_BUFFER_CAPACITY,
    opciones: CircularBufferOptions = {},
  ) {
    this.maxBytes = opciones.maxBytes ?? DEFAULT_BUFFER_MAX_BYTES;
    this.alAvisar = opciones.alAvisar ?? (() => {});
  }

  /**
   * Lee el estado agregado del store UNA sola vez (perezoso, en el primer uso) y
   * de ahi en mas lo mantiene incremental.
   *
   * Ademas resuelve el bug de orden post-reload: ``nextSeq`` continua desde el
   * mayor ``seq`` que quedo guardado, en vez de volver a cero y numerar los
   * eventos nuevos por debajo de los que estaban esperando.
   */
  private async iniciar(): Promise<void> {
    if (!this.arranque) {
      this.arranque = (async () => {
        const { bytes, maxSeq } = await this.store.resumen();
        this.bytesUsados = bytes;
        this.nextSeq = maxSeq + 1;
      })();
    }
    return this.arranque;
  }

  /**
   * Persiste un evento en el buffer antes de enviarlo. Asigna un ``seq`` local
   * monotono para preservar el orden de produccion. Si no entra en el presupuesto
   * (o en la capacidad), descarta los mas viejos — avisando — hasta hacerle lugar.
   *
   * Idempotente por ``id``: re-bufferizar el mismo ``event_id`` no duplica (no se
   * le asigna un nuevo seq); mantiene exactly-once logico en el lado del cliente.
   *
   * NUNCA lanza: un fallo de almacenamiento no puede tumbar el examen del alumno.
   * Lo reporta por ``alAvisar`` para que la UI lo haga visible.
   */
  async append(id: string, message: object): Promise<void> {
    await this.iniciar();
    if (await this.store.get(id)) return; // ya bufferizado: no duplicar

    const bytes = pesoAproximado(message);
    await this.hacerLugar(bytes);

    try {
      await this.store.put({ id, message, seq: this.nextSeq, bytes });
    } catch (err) {
      // Cuota agotada o store caido. El evento no quedo guardado: que se sepa.
      this.alAvisar("sin-espacio", err);
      return;
    }
    this.nextSeq += 1;
    this.bytesUsados += bytes;
    this.pesos.set(id, bytes);
  }

  /**
   * Expulsa los mas viejos hasta que ``bytes`` entre en el presupuesto y en la
   * capacidad. El evento NUEVO siempre entra: lo ultimo que paso es lo que mas
   * cerca esta de explicar por que se corto.
   */
  private async hacerLugar(bytes: number): Promise<void> {
    let cantidad = await this.store.count();
    while (
      cantidad > 0 &&
      (this.bytesUsados + bytes > this.maxBytes || cantidad >= this.capacity)
    ) {
      const viejo = await this.store.oldest();
      if (!viejo) break;
      await this.store.delete(viejo.id);
      this.pesos.delete(viejo.id);
      this.bytesUsados = Math.max(0, this.bytesUsados - (viejo.bytes ?? 0));
      cantidad -= 1;
      this.alAvisar("expulsado", viejo.id);
    }
  }

  /** Registros pendientes en ORDEN de produccion (seq ascendente). */
  async pending(): Promise<BufferedEvent[]> {
    return this.store.getAllOrdered();
  }

  /** Marca un evento como confirmado (persistido por el backend) y lo purga. */
  async confirm(id: string): Promise<void> {
    await this.iniciar();
    const bytes = this.pesos.get(id) ?? (await this.store.get(id))?.bytes ?? 0;
    await this.store.delete(id);
    this.pesos.delete(id);
    this.bytesUsados = Math.max(0, this.bytesUsados - bytes);
  }

  async size(): Promise<number> {
    return this.store.count();
  }

  /** Peso actual del buffer en bytes (para diagnostico y para la UI). */
  async bytes(): Promise<number> {
    await this.iniciar();
    return this.bytesUsados;
  }
}

/**
 * Adaptador en memoria del puerto (para tests). NO usar en produccion: no
 * sobrevive refresh. Mantiene insercion por ``seq`` y respeta el contrato del
 * puerto (orden ascendente).
 */
export class InMemoryEventBufferStore implements EventBufferStore {
  private records = new Map<string, BufferedEvent>();

  async put(record: BufferedEvent): Promise<void> {
    this.records.set(record.id, { ...record });
  }

  async get(id: string): Promise<BufferedEvent | null> {
    return this.records.get(id) ?? null;
  }

  async getAllOrdered(): Promise<BufferedEvent[]> {
    return [...this.records.values()].sort((a, b) => a.seq - b.seq);
  }

  async delete(id: string): Promise<void> {
    this.records.delete(id);
  }

  async count(): Promise<number> {
    return this.records.size;
  }

  async oldest(): Promise<BufferedEvent | null> {
    const ordered = await this.getAllOrdered();
    return ordered.length > 0 ? ordered[0] : null;
  }

  async resumen(): Promise<{ bytes: number; maxSeq: number }> {
    let bytes = 0;
    let maxSeq = -1;
    for (const r of this.records.values()) {
      bytes += r.bytes ?? 0;
      if (r.seq > maxSeq) maxSeq = r.seq;
    }
    return { bytes, maxSeq };
  }
}
