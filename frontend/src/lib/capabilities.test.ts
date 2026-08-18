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
  it("revisar_sesion cubre TODO el acto (aprobar y anular) para coordinador y admin_sistema", () => {
    // c-76: el rol "revisor" fue eliminado; el coordinador absorbe el veredicto.
    expect(tieneCapacidad(["coordinador"], "revisar_sesion")).toBe(true);
    expect(tieneCapacidad(["admin_sistema"], "revisar_sesion")).toBe(true);
    expect(tieneCapacidad(["tutor"], "revisar_sesion")).toBe(false);
  });

  it("el tutor gestiona lo académico y supervisa en vivo (acotado a su comisión), pero NUNCA emite veredicto", () => {
    // c-76 D2/D3: el tutor SI tiene supervisar_vivo (el scoping por comisión lo
    // aplica el backend, autorizar_supervision_vivo_sobre_sesion — el front solo
    // decide si el item/ruta se muestra), pero revisar_sesion (el veredicto)
    // sigue siendo exclusivo de coordinador/admin_sistema.
    expect(tieneCapacidad(["tutor"], "gestionar_academico")).toBe(true);
    expect(tieneCapacidad(["tutor"], "gestionar_notas")).toBe(true);
    expect(tieneCapacidad(["tutor"], "revisar_sesion")).toBe(false);
    expect(tieneCapacidad(["tutor"], "supervisar_vivo")).toBe(true);
    expect(tieneCapacidad(["tutor"], "configurar_sistema")).toBe(false);
  });

  it("estudiante no tiene ninguna capacidad de revisión", () => {
    expect(tieneCapacidad(["estudiante"], "revisar_sesion")).toBe(false);
  });

  it("capacidad desconocida → deniega (fail-closed)", () => {
    // @ts-expect-error capacidad fuera del union: el helper deniega igual
    expect(tieneCapacidad(["admin_sistema"], "capacidad_inexistente")).toBe(false);
  });

  it("sin roles → deniega", () => {
    expect(tieneCapacidad([], "revisar_sesion")).toBe(false);
  });
});
