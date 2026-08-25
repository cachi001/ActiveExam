/**
 * Tests del envio con respaldo y del reintento de drenaje (c-78).
 *
 * El patron "guardar antes de mandar, purgar recien cuando el backend contesta"
 * vivia escrito a mano dentro de `useExamProctoring`, y por eso la captura de
 * pausa —que es otro camino de envio— no lo tenia. Extraido aca, es uno solo y
 * se puede probar sin montar el examen entero.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CircularEventBuffer, InMemoryEventBufferStore } from "./eventBuffer";
import {
  INTERVALO_REINTENTO_DRENAJE_MS,
  crearEnvioReintentable,
  crearReintentoDeDrenaje,
  enviarConRespaldo,
} from "./envioConRespaldo";

function buf() {
  const store = new InMemoryEventBufferStore();
  return { store, buffer: new CircularEventBuffer(store) };
}

describe("enviarConRespaldo", () => {
  it("purga del buffer recien cuando el backend confirmo", async () => {
    const { buffer } = buf();
    const enviar = vi.fn().mockResolvedValue(undefined);

    const res = await enviarConRespaldo(buffer, "e1", { tipo: "x" }, enviar);

    expect(res.enviado).toBe(true);
    expect(await buffer.size()).toBe(0);
    expect(enviar).toHaveBeenCalledWith({ tipo: "x" });
  });

  it("si el POST falla, el evento queda bufferizado para el replay", async () => {
    const { buffer } = buf();
    const enviar = vi.fn().mockRejectedValue(new Error("red caida"));

    const res = await enviarConRespaldo(buffer, "e1", { tipo: "x" }, enviar);

    expect(res.enviado).toBe(false);
    expect((await buffer.pending()).map((e) => e.id)).toEqual(["e1"]);
  });

  it("guarda ANTES de mandar, no despues", async () => {
    // Si guardara despues, un corte justo en el POST perderia el evento: es el
    // caso exacto que el buffer existe para cubrir.
    const { buffer } = buf();
    let habiaEnBufferAlMandar = 0;
    const enviar = vi.fn(async () => {
      habiaEnBufferAlMandar = await buffer.size();
      throw new Error("red caida");
    });

    await enviarConRespaldo(buffer, "e1", {}, enviar);

    expect(habiaEnBufferAlMandar).toBe(1);
  });

  it("sin buffer (IndexedDB no disponible) igual manda", async () => {
    const enviar = vi.fn().mockResolvedValue(undefined);
    const res = await enviarConRespaldo(null, "e1", { tipo: "x" }, enviar);
    expect(res.enviado).toBe(true);
    expect(enviar).toHaveBeenCalledOnce();
  });

  it("nunca propaga el error: el examen del alumno no se cae por esto", async () => {
    const { buffer } = buf();
    const enviar = vi.fn().mockRejectedValue(new Error("500"));
    await expect(enviarConRespaldo(buffer, "e1", {}, enviar)).resolves.toEqual({
      enviado: false,
    });
  });
});

describe("crearEnvioReintentable", () => {
  it("si sale bien no queda nada pendiente", async () => {
    const enviar = vi.fn().mockResolvedValue(undefined);
    const envio = crearEnvioReintentable<{ v: number }>({ enviar });

    expect(await envio.enviar({ v: 1 })).toBe(true);
    expect(envio.hayPendiente()).toBe(false);
  });

  it("si falla, el valor QUEDA pendiente (no se pierde)", async () => {
    // El bug real: el llamador limpiaba el payload biométrico apenas disparaba el
    // POST, sin esperar el resultado. Un hipo de red al arrancar el examen —justo
    // cuando entran todos a la vez— borraba la verificación de identidad del
    // alumno para siempre. Acá el valor solo se suelta cuando el backend contestó.
    const enviar = vi.fn().mockRejectedValue(new Error("red caida"));
    const envio = crearEnvioReintentable<{ v: number }>({ enviar });

    expect(await envio.enviar({ v: 1 })).toBe(false);
    expect(envio.hayPendiente()).toBe(true);
  });

  it("reintentar() manda lo que quedó y recién ahí lo suelta", async () => {
    const enviar = vi
      .fn()
      .mockRejectedValueOnce(new Error("red caida"))
      .mockResolvedValue(undefined);
    const envio = crearEnvioReintentable<{ v: number }>({ enviar });

    await envio.enviar({ v: 1 });
    await envio.reintentar();

    expect(enviar).toHaveBeenCalledTimes(2);
    expect(enviar).toHaveBeenLastCalledWith({ v: 1 });
    expect(envio.hayPendiente()).toBe(false);
  });

  it("reintentar() sin nada pendiente no toca la red", async () => {
    const enviar = vi.fn().mockResolvedValue(undefined);
    const envio = crearEnvioReintentable<{ v: number }>({ enviar });

    await envio.reintentar();

    expect(enviar).not.toHaveBeenCalled();
  });

  it("un valor nuevo pisa al pendiente: manda el más reciente", async () => {
    // En biometría el pendiente es una verificación de identidad: si el alumno se
    // re-verificó, la que vale es la última, no la vieja que no pudo salir.
    const enviar = vi.fn().mockRejectedValue(new Error("red caida"));
    const envio = crearEnvioReintentable<{ v: number }>({ enviar });

    await envio.enviar({ v: 1 });
    await envio.enviar({ v: 2 });
    enviar.mockResolvedValue(undefined);
    await envio.reintentar();

    expect(enviar).toHaveBeenLastCalledWith({ v: 2 });
  });

  it("nunca propaga el error", async () => {
    const enviar = vi.fn().mockRejectedValue(new Error("500"));
    const envio = crearEnvioReintentable<number>({ enviar });
    await expect(envio.enviar(1)).resolves.toBe(false);
    await expect(envio.reintentar()).resolves.toBeUndefined();
  });
});

describe("crearReintentoDeDrenaje", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("reintenta solo, sin esperar el evento 'online' del navegador", async () => {
    // El agujero real: el drenaje colgaba unicamente de window.'online'. Si al
    // alumno se le corta y vuelve SIN que el navegador dispare ese evento (o si
    // recarga la pagina despues del corte, que es lo que hace cualquiera), lo
    // bufferizado no se reenviaba nunca.
    const drenar = vi.fn().mockResolvedValue(undefined);
    const ctrl = crearReintentoDeDrenaje({ drenar });

    ctrl.arrancar();
    await vi.advanceTimersByTimeAsync(INTERVALO_REINTENTO_DRENAJE_MS * 3);

    expect(drenar.mock.calls.length).toBeGreaterThanOrEqual(3);
  });

  it("drena una vez al arrancar, para lo que quedo de la sesion anterior", async () => {
    const drenar = vi.fn().mockResolvedValue(undefined);
    crearReintentoDeDrenaje({ drenar }).arrancar();

    await vi.advanceTimersByTimeAsync(0);

    expect(drenar).toHaveBeenCalledOnce();
  });

  it("detener() corta el timer (no deja huerfanos al desmontar)", async () => {
    const drenar = vi.fn().mockResolvedValue(undefined);
    const ctrl = crearReintentoDeDrenaje({ drenar });

    ctrl.arrancar();
    await vi.advanceTimersByTimeAsync(0);
    ctrl.detener();
    const llamadasAlCortar = drenar.mock.calls.length;
    await vi.advanceTimersByTimeAsync(INTERVALO_REINTENTO_DRENAJE_MS * 5);

    expect(drenar.mock.calls.length).toBe(llamadasAlCortar);
  });

  it("un drenaje que falla no mata el reintento", async () => {
    const drenar = vi.fn().mockRejectedValue(new Error("sigue sin red"));
    const ctrl = crearReintentoDeDrenaje({ drenar });

    ctrl.arrancar();
    await vi.advanceTimersByTimeAsync(INTERVALO_REINTENTO_DRENAJE_MS * 3);
    ctrl.detener();

    expect(drenar.mock.calls.length).toBeGreaterThanOrEqual(3);
  });

  it("no encima drenajes: espera a que termine el anterior", async () => {
    // Con la red caida un drenaje tarda (timeouts de POST). Si el timer dispara
    // igual, se apilan replays del mismo backlog contra el mismo backend.
    let enVuelo = 0;
    let maxSimultaneos = 0;
    const drenar = vi.fn(async () => {
      enVuelo += 1;
      maxSimultaneos = Math.max(maxSimultaneos, enVuelo);
      await new Promise((r) => setTimeout(r, INTERVALO_REINTENTO_DRENAJE_MS * 2));
      enVuelo -= 1;
    });
    const ctrl = crearReintentoDeDrenaje({ drenar });

    ctrl.arrancar();
    await vi.advanceTimersByTimeAsync(INTERVALO_REINTENTO_DRENAJE_MS * 6);
    ctrl.detener();

    expect(maxSimultaneos).toBe(1);
  });
});
