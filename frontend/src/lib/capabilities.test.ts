/**
 * Tests del helper de capacidades del front (C-71 slice 2, D8).
 *
 * El backend es el que DECIDE (backstop server-side): este helper solo decide
 * qué OCULTA el front. Espeja el mapa `capacidad → roles` del backend adaptado
 * al modelo de 3 roles del MVP (revisor colapsado en admin_sistema).
 */

import { describe, expect, it } from "vitest";
import { tieneCapacidad } from "./capabilities";

describe("tieneCapacidad — gating por capacidad (front-hides)", () => {
  it("admin_sistema tiene resolver_caso (revisor colapsado en admin_sistema)", () => {
    expect(tieneCapacidad(["admin_sistema"], "resolver_caso")).toBe(true);
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
