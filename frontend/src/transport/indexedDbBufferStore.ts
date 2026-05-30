/**
 * Adaptador IndexedDB del puerto ``EventBufferStore`` (C-14, D1).
 *
 * Implementacion de PRODUCCION: persiste el buffer en IndexedDB para que sobreviva
 * a refresh / cierre de pestaña (RN-HB-02). Solo I/O — toda la logica de orden,
 * circularidad y deduplicacion vive en ``CircularEventBuffer`` (puro, testeado).
 *
 * No se testea con harness unitario (requiere IndexedDB del navegador); su
 * contrato esta cubierto por el adaptador en memoria. Verificable en e2e/browser.
 */

import type { BufferedEvent, EventBufferStore } from "./eventBuffer";

const DB_NAME = "proctoring-event-buffer";
const STORE_NAME = "events";
const DB_VERSION = 1;

export class IndexedDbEventBufferStore implements EventBufferStore {
  private dbPromise: Promise<IDBDatabase> | null = null;

  constructor(private readonly indexedDB: IDBFactory = globalThis.indexedDB) {}

  private open(): Promise<IDBDatabase> {
    if (this.dbPromise) return this.dbPromise;
    this.dbPromise = new Promise<IDBDatabase>((resolve, reject) => {
      const req = this.indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: "id" });
          store.createIndex("seq", "seq", { unique: false });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return this.dbPromise;
  }

  private async tx<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
    const db = await this.open();
    return new Promise<T>((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, mode);
      const request = fn(transaction.objectStore(STORE_NAME));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async put(record: BufferedEvent): Promise<void> {
    await this.tx("readwrite", (store) => store.put(record));
  }

  async getAllOrdered(): Promise<BufferedEvent[]> {
    const all = await this.tx<BufferedEvent[]>("readonly", (store) => store.getAll() as IDBRequest<BufferedEvent[]>);
    return all.sort((a, b) => a.seq - b.seq);
  }

  async delete(id: string): Promise<void> {
    await this.tx("readwrite", (store) => store.delete(id));
  }

  async count(): Promise<number> {
    return this.tx<number>("readonly", (store) => store.count());
  }

  async oldestId(): Promise<string | null> {
    const ordered = await this.getAllOrdered();
    return ordered.length > 0 ? ordered[0].id : null;
  }
}
