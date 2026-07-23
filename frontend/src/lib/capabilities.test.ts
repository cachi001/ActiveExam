/**
 * Tests del helper de capacidades del front (C-71 slice 2, D8).
 *
 * El backend es el que DECIDE (backstop server-side): este helper solo decide
 * qué OCULTA el front. Es una COPIA EXACTA del mapa `capacidad → roles` del
 * backend (`app/domain/auth/capabilities.py`): si se separan, el front muestra
 * botones que el backend rechaza con 403 — o esconde acciones permitidas.
 */

import { describe, expect, it } from "vitest";
import { tieneCapacidad } from "./capabilities";

describe("tieneCapacidad — gating por capacidad (front-hides)", () => {
  it("resolver_caso es EXCLUSIVA del revisor", () => {
    // Quien pone la nota o administra el sistema no decide el fraude.
    expect(tieneCapacidad(["revisor"], "resolver_caso")).toBe(true);
    expect(tieneCapacidad(["admin_sistema"], "resolver_caso")).toBe(false);
    expect(tieneCapacidad(["docente"], "resolver_caso")).toBe(false);
  });

  it("el docente gestiona lo académico pero NO revisa ni supervisa", () => {
    expect(tieneCapacidad(["docente"], "gestionar_academico")).toBe(true);
    expect(tieneCapacidad(["docente"], "gestionar_notas")).toBe(true);
    expect(tieneCapacidad(["docente"], "revisar_sesion")).toBe(false);
    expect(tieneCapacidad(["docente"], "supervisar_vivo")).toBe(false);
    expect(tieneCapacidad(["docente"], "configurar_sistema")).toBe(false);
  });

  it("admin_sistema tiene revisar_sesion", () => {
    expect(tieneCapacidad(["admin_sistema"], "revisar_sesion")).toBe(true);
  });

  it("estudiante no tiene ninguna capacidad de revisión", () => {
    expect(tieneCapacidad(["estudiante"], "resolver_caso")).toBe(false);
    expect(tieneCapacidad(["estudiante"], "revisar_sesion")).toBe(false);
  });

  it("proctor no tiene resolver_caso (supervisa en vivo, no resuelve)", () => {
    expect(tieneCapacidad(["proctor"], "resolver_caso")).toBe(false);
  });

  it("capacidad desconocida → deniega (fail-closed)", () => {
    // @ts-expect-error capacidad fuera del union: el helper deniega igual
    expect(tieneCapacidad(["admin_sistema"], "capacidad_inexistente")).toBe(false);
  });

  it("sin roles → deniega", () => {
    expect(tieneCapacidad([], "resolver_caso")).toBe(false);
  });
});
