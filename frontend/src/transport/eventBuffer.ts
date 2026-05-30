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
 */

/** Evento bufferizado: el contrato firmado de C-10 + un seq local monotono. */
export interface BufferedEvent {
  /** ``event_id`` del contrato (clave de deduplicacion, RN-HB-03). */
  id: string;
  /** Mensaje serializado tal cual se enviara por el WS (firmado). */
  message: object;
  /** Secuencia local monotona; fija el ORDEN de produccion (replay ordenado). */
  seq: number;
}

/**
 * Puerto de almacenamiento del buffer. El adaptador concreto (IndexedDB o memoria)
 * solo persiste/lee/borra; el orden y la circularidad los gobierna el buffer.
 */
export interface EventBufferStore {
  put(record: BufferedEvent): Promise<void>;
  /** Todos los registros, en orden ascendente de ``seq``. */
  getAllOrdered(): Promise<BufferedEvent[]>;
  /** Borra por ``id`` (confirmacion/purga). */
  delete(id: string): Promise<void>;
  /** Cantidad actual de registros. */
  count(): Promise<number>;
  /** ``id`` del registro mas viejo (menor ``seq``), o null si vacio. */
  oldestId(): Promise<string | null>;
}

export const DEFAULT_BUFFER_CAPACITY = 10_000;

export class CircularEventBuffer {
  private nextSeq = 0;

  constructor(
    private readonly store: EventBufferStore,
    private readonly capacity: number = DEFAULT_BUFFER_CAPACITY,
  ) {}

  /**
   * Persiste un evento en el buffer antes de enviarlo. Asigna un ``seq`` local
   * monotono para preservar el orden de produccion. Si se alcanza la capacidad,
   * descarta el registro mas viejo (buffer circular, D1).
   *
   * Idempotente por ``id``: re-bufferizar el mismo ``event_id`` no duplica (no se
   * le asigna un nuevo seq); mantiene exactly-once logico en el lado del cliente.
   */
  async append(id: string, message: object): Promise<void> {
    const existing = await this.store.getAllOrdered();
    if (existing.some((e) => e.id === id)) return; // ya bufferizado: no duplicar

    if (existing.length >= this.capacity) {
      const oldest = await this.store.oldestId();
      if (oldest !== null) await this.store.delete(oldest);
    }
    const seq = this.nextSeq++;
    await this.store.put({ id, message, seq });
  }

  /** Registros pendientes en ORDEN de produccion (seq ascendente). */
  async pending(): Promise<BufferedEvent[]> {
    return this.store.getAllOrdered();
  }

  /** Marca un evento como confirmado (persistido por el backend) y lo purga. */
  async confirm(id: string): Promise<void> {
    await this.store.delete(id);
  }

  async size(): Promise<number> {
    return this.store.count();
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

  async getAllOrdered(): Promise<BufferedEvent[]> {
    return [...this.records.values()].sort((a, b) => a.seq - b.seq);
  }

  async delete(id: string): Promise<void> {
    this.records.delete(id);
  }

  async count(): Promise<number> {
    return this.records.size;
  }

  async oldestId(): Promise<string | null> {
    const ordered = await this.getAllOrdered();
    return ordered.length > 0 ? ordered[0].id : null;
  }
}
