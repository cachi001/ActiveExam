/**
 * Tests de la politica por duracion del corte (C-14, RN-HB-04, RN-EV-04, L2.5).
 * Formato Vitest.
 *
 * Verifica: deteccion de duracion via heartbeats, corte corto sin evento extra,
 * corte largo -> evento critico, y la INVARIANTE L2.5 (señal, nunca sancion).
 */

import { describe, expect, it } from "vitest";

import {
  classifyOutage,
  isProlongedOutage,
  OUTAGE_THRESHOLD_MS,
  outageDurationMs,
  PROLONGED_OUTAGE_EVENT_TIPO,
} from "./outagePolicy";

const MIN = 60 * 1000;

describe("deteccion de duracion (4.1)", () => {
  it("mide el corte como reconexion - ultimo heartbeat", () => {
    expect(outageDurationMs(1000, 1000 + 3 * MIN)).toBe(3 * MIN);
  });

  it("nunca es negativa (reloj desordenado)", () => {
    expect(outageDurationMs(5000, 1000)).toBe(0);
  });

  it("el umbral del dominio es 5 minutos", () => {
    expect(OUTAGE_THRESHOLD_MS).toBe(5 * MIN);
  });
});

describe("corte corto < 5 min sin perdida (4.2)", () => {
  it("no emite evento critico para un corte de 4 min", () => {
    const ev = classifyOutage(0, 4 * MIN);
    expect(ev).toBeNull();
  });

  it("exactamente 5 min NO se considera prolongado (umbral estricto >)", () => {
    expect(isProlongedOutage(5 * MIN)).toBe(false);
    expect(classifyOutage(0, 5 * MIN)).toBeNull();
  });
});

describe("corte largo > 5 min -> evento critico (4.3)", () => {
  it("emite el evento critico de corte prolongado", () => {
    const ev = classifyOutage(0, 6 * MIN);
    expect(ev).not.toBeNull();
    expect(ev!.tipo).toBe(PROLONGED_OUTAGE_EVENT_TIPO);
    expect(ev!.severidad).toBe("critica");
    expect(ev!.outage_ms).toBe(6 * MIN);
  });
});

describe("invariante L2.5: señal, nunca sancion (4.4, RN-RV-07)", () => {
  it("el evento critico es solo señal (signal_only) y no contiene sancion", () => {
    const ev = classifyOutage(0, 10 * MIN)!;
    expect(ev.signal_only).toBe(true);
    // ningun campo del evento implica una sancion automatica
    expect(Object.keys(ev)).not.toContain("sancion");
    expect(Object.keys(ev)).not.toContain("penalizacion");
    expect(Object.keys(ev)).not.toContain("veredicto");
  });
});
