/**
 * Tests del helper compartido faceCountLabel (C-53, harness-legibility-layer).
 *
 * Verifica la pluralización en los bordes (0/1/N) y el fraseo rotulado por
 * origen (cliente/servidor), que es la fuente ÚNICA de presentación del
 * conteo de rostros en toda la UI.
 */

import { describe, expect, it } from "vitest";
import { formatRostros, formatRostrosConOrigen } from "./faceCountLabel";

describe("formatRostros — pluralización en los bordes", () => {
  it("0 → 'sin rostros'", () => {
    expect(formatRostros(0)).toBe("sin rostros");
  });

  it("1 → '1 rostro detectado'", () => {
    expect(formatRostros(1)).toBe("1 rostro detectado");
  });

  it("2 → '2 rostros detectados'", () => {
    expect(formatRostros(2)).toBe("2 rostros detectados");
  });

  it("N grande → 'N rostros detectados'", () => {
    expect(formatRostros(5)).toBe("5 rostros detectados");
  });

  it("null/undefined → '—' (sin dato)", () => {
    expect(formatRostros(null)).toBe("—");
    expect(formatRostros(undefined)).toBe("—");
  });
});

describe("formatRostrosConOrigen — fraseo rotulado cliente/servidor", () => {
  it("Servidor, 2 → 'Servidor: 2 rostros'", () => {
    expect(formatRostrosConOrigen("Servidor", 2)).toBe("Servidor: 2 rostros");
  });

  it("Cliente, 1 → 'Cliente: 1 rostro'", () => {
    expect(formatRostrosConOrigen("Cliente", 1)).toBe("Cliente: 1 rostro");
  });

  it("Servidor, 0 → 'Servidor: sin rostros'", () => {
    expect(formatRostrosConOrigen("Servidor", 0)).toBe("Servidor: sin rostros");
  });

  it("no usa el prefijo técnico crudo 'srv:'", () => {
    expect(formatRostrosConOrigen("Servidor", 2)).not.toContain("srv:");
  });

  it("null/undefined → '{origen}: —'", () => {
    expect(formatRostrosConOrigen("Cliente", null)).toBe("Cliente: —");
    expect(formatRostrosConOrigen("Servidor", undefined)).toBe("Servidor: —");
  });
});
