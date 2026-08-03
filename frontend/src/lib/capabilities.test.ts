/**
 * Tests del helper de capacidades del front (C-71 slice 2, D8, modelo de un
 * solo paso — no hay capacidad `resolver_caso` separada).
 *
 * El backend es el que DECIDE (backstop server-side): este helper solo decide
 * qué OCULTA el front. Es una COPIA EXACTA del mapa `capacidad → roles` del
 * backend (`app/domain/auth/capabilities.py`): si se separan, el front muestra
 * botones que el backend rechaza con 403 — o esconde acciones permitidas.
 */

import { describe, expect, it } from "vitest";
import { tieneCapacidad } from "./capabilities";

describe("tieneCapacidad — gating por capacidad (front-hides)", () => {
  it("revisar_sesion cubre TODO el acto (aprobar y anular) para revisor, coordinador y admin_sistema", () => {
    expect(tieneCapacidad(["revisor"], "revisar_sesion")).toBe(true);
    expect(tieneCapacidad(["coordinador"], "revisar_sesion")).toBe(true);
    expect(tieneCapacidad(["admin_sistema"], "revisar_sesion")).toBe(true);
    expect(tieneCapacidad(["docente"], "revisar_sesion")).toBe(false);
  });

  it("el docente gestiona lo académico pero NO revisa ni supervisa", () => {
    expect(tieneCapacidad(["docente"], "gestionar_academico")).toBe(true);
    expect(tieneCapacidad(["docente"], "gestionar_notas")).toBe(true);
    expect(tieneCapacidad(["docente"], "revisar_sesion")).toBe(false);
    expect(tieneCapacidad(["docente"], "supervisar_vivo")).toBe(false);
    expect(tieneCapacidad(["docente"], "configurar_sistema")).toBe(false);
  });

  it("estudiante no tiene ninguna capacidad de revisión", () => {
    expect(tieneCapacidad(["estudiante"], "revisar_sesion")).toBe(false);
  });

  it("proctor no tiene revisar_sesion (supervisa en vivo, no decide)", () => {
    expect(tieneCapacidad(["proctor"], "revisar_sesion")).toBe(false);
  });

  it("capacidad desconocida → deniega (fail-closed)", () => {
    // @ts-expect-error capacidad fuera del union: el helper deniega igual
    expect(tieneCapacidad(["admin_sistema"], "capacidad_inexistente")).toBe(false);
  });

  it("sin roles → deniega", () => {
    expect(tieneCapacidad([], "revisar_sesion")).toBe(false);
  });
});
