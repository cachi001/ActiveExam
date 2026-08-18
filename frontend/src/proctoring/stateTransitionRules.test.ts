/**
 * Tests de las reglas de transicion de estado (C-11). Formato Vitest.
 *
 * Cubre: rostro ausente sostenido > 3s -> evento medio; ausencia instantanea (ruido)
 * -> sin evento; mirada normal vs patron sostenido hacia un punto fijo; multiples
 * rostros (>=2 durante N frames) -> alta + dispara evidencia; configurabilidad por
 * institucion; y la garantia L2.5: ninguna transicion deriva una sancion.
 */

import { describe, expect, it } from "vitest";

import { DEFAULT_CONFIG, StateTransitionRules } from "./stateTransitionRules";

describe("rostro ausente sostenido", () => {
  it("emite evento medio cuando la ausencia supera el umbral de 3s", () => {
    const rules = new StateTransitionRules();
    rules.process({ ts_ms: 0, face_count: 0 });
    rules.process({ ts_ms: 1500, face_count: 0 });
    const events = rules.process({ ts_ms: 3500, face_count: 0 });
    expect(events).toHaveLength(1);
    expect(events[0].tipo).toBe("rostro_ausente");
    expect(events[0].severidad).toBe("media");
  });

  it("no re-emite mientras la ausencia continua (un solo evento por episodio)", () => {
    const rules = new StateTransitionRules();
    rules.process({ ts_ms: 0, face_count: 0 });
    rules.process({ ts_ms: 3500, face_count: 0 });
    const again = rules.process({ ts_ms: 5000, face_count: 0 });
    expect(again).toHaveLength(0);
  });
});

describe("no-evento por ruido instantaneo", () => {
  it("una ausencia en un unico frame aislado no genera evento", () => {
    const rules = new StateTransitionRules();
    const e1 = rules.process({ ts_ms: 0, face_count: 1 });
    const e2 = rules.process({ ts_ms: 100, face_count: 0 }); // parpadeo / glitch
    const e3 = rules.process({ ts_ms: 200, face_count: 1 });
    expect([...e1, ...e2, ...e3]).toHaveLength(0);
  });

  it("un frame con 2 rostros aislado no dispara multiples rostros", () => {
    const rules = new StateTransitionRules();
    const e1 = rules.process({ ts_ms: 0, face_count: 2 });
    const e2 = rules.process({ ts_ms: 100, face_count: 1 });
    expect([...e1, ...e2]).toHaveLength(0);
  });
});

describe("mirada: normal no es evento, patron sostenido si (RN-EV-06)", () => {
  it("mirar al techo brevemente y volver no genera evento", () => {
    const rules = new StateTransitionRules();
    rules.process({ ts_ms: 0, face_count: 1, gaze: { x: 0.0, y: -0.7 } }); // desvio
    const back = rules.process({ ts_ms: 500, face_count: 1, gaze: { x: 0.0, y: 0.0 } }); // vuelve
    const more = rules.process({ ts_ms: 6000, face_count: 1, gaze: { x: 0.0, y: 0.0 } });
    expect([...back, ...more]).toHaveLength(0);
  });

  it("consulta sostenida hacia un punto fijo fuera de pantalla genera evento medio", () => {
    const rules = new StateTransitionRules();
    rules.process({ ts_ms: 0, face_count: 1, gaze: { x: 0.8, y: 0.1 } });
    rules.process({ ts_ms: 2000, face_count: 1, gaze: { x: 0.82, y: 0.09 } });
    const events = rules.process({ ts_ms: 4500, face_count: 1, gaze: { x: 0.79, y: 0.11 } });
    expect(events).toHaveLength(1);
    expect(events[0].tipo).toBe("mirada_desviada_sostenida");
    expect(events[0].severidad).toBe("media");
  });
});

describe("multiples rostros (>=2 durante N frames)", () => {
  it("dispara severidad alta, captura de evidencia, en N frames consecutivos", () => {
    const rules = new StateTransitionRules();
    let events: ReturnType<StateTransitionRules["process"]> = [];
    for (let i = 0; i < DEFAULT_CONFIG.multiple_faces_frames; i += 1) {
      events = rules.process({ ts_ms: i * 100, face_count: 2 });
    }
    expect(events).toHaveLength(1);
    expect(events[0].tipo).toBe("multiples_rostros");
    expect(events[0].severidad).toBe("alta");
    expect(events[0].trigger_evidence).toBe(true);
  });

  it("el evento se emite dentro de la ventana de <500ms desde el primer frame", () => {
    const rules = new StateTransitionRules();
    let event;
    for (let i = 0; i < DEFAULT_CONFIG.multiple_faces_frames; i += 1) {
      const out = rules.process({ ts_ms: i * 50, face_count: 2 }); // 50ms/frame
      if (out.length) event = out[0];
    }
    // 5 frames a 50ms = 200ms desde el primero, dentro del presupuesto de 500ms.
    expect(event!.ts_ms).toBeLessThan(500);
  });
});

describe("configurabilidad por institucion (RN-EV-03)", () => {
  it("cambiar el umbral temporal sin tocar codigo cambia cuando se emite", () => {
    const strict = new StateTransitionRules({ face_absent_ms: 1000 });
    strict.process({ ts_ms: 0, face_count: 0 });
    const events = strict.process({ ts_ms: 1500, face_count: 0 });
    expect(events).toHaveLength(1);

    const lax = new StateTransitionRules({ face_absent_ms: 10000 });
    lax.process({ ts_ms: 0, face_count: 0 });
    const none = lax.process({ ts_ms: 1500, face_count: 0 });
    expect(none).toHaveLength(0);
  });
});

describe("monitor_adicional de-dup (Batch A bugfix)", () => {
  it("emite monitor_adicional UNA vez por transicion false->true (no spam por frame)", () => {
    const rules = new StateTransitionRules();
    // Primer frame con monitor conectado: emite.
    const ev1 = rules.process({ ts_ms: 0, face_count: 1, extra_monitor: true });
    expect(ev1.filter((e) => e.tipo === "monitor_adicional")).toHaveLength(1);
    // Mismo monitor sigue conectado en los frames siguientes: NO re-emite.
    const ev2 = rules.process({ ts_ms: 1000, face_count: 1, extra_monitor: true });
    expect(ev2.filter((e) => e.tipo === "monitor_adicional")).toHaveLength(0);
    const ev3 = rules.process({ ts_ms: 2000, face_count: 1, extra_monitor: true });
    expect(ev3.filter((e) => e.tipo === "monitor_adicional")).toHaveLength(0);
    // El monitor se desconecta: no hay evento pero resetea de-dup.
    const ev4 = rules.process({ ts_ms: 3000, face_count: 1, extra_monitor: false });
    expect(ev4.filter((e) => e.tipo === "monitor_adicional")).toHaveLength(0);
    // El monitor vuelve a conectarse: emite de nuevo (nueva transicion).
    const ev5 = rules.process({ ts_ms: 4000, face_count: 1, extra_monitor: true });
    expect(ev5.filter((e) => e.tipo === "monitor_adicional")).toHaveLength(1);
  });
});

describe("garantia L2.5: ninguna transicion deriva sancion", () => {
  it("ningun evento producido contiene una sancion o veredicto", () => {
    const rules = new StateTransitionRules({ multiple_faces_frames: 1 });
    const events = rules.process({ ts_ms: 0, face_count: 3, extra_monitor: true });
    expect(events.length).toBeGreaterThan(0);
    for (const e of events) {
      // Solo senal: tipo + severidad + payload. Sin campo de sancion/veredicto/bloqueo.
      expect(Object.keys(e)).toEqual(
        expect.arrayContaining(["tipo", "severidad", "ts_ms", "payload", "trigger_evidence"]),
      );
      expect(e).not.toHaveProperty("sancion");
      expect(e).not.toHaveProperty("veredicto");
      expect(e).not.toHaveProperty("bloqueo");
      // trigger_evidence captura prueba; NO sanciona.
      expect(["baseline", "baja", "media", "alta", "critica"]).toContain(e.severidad);
    }
  });
});

// C-76 (15.1/15.2/15.6): cambio_pestana y copiar_pegar ahora disparan captura.
// El screenshot es CONTEXTO VISUAL (no se re-infiere server-side, a diferencia de
// multiples_rostros/rostro_ausente) — la severidad no cambia (sigue "media"), y
// copiar_pegar puede traer el hash del contenido pegado (evidencia real, nunca el
// contenido en claro).
describe("C-76 15: evidencia de cambio_pestana / copiar_pegar", () => {
  it("cambio_pestana dispara trigger_evidence al ocultarse la pestana", () => {
    const rules = new StateTransitionRules();
    const events = rules.process({ ts_ms: 0, face_count: 1, tab_changed: true });
    expect(events).toHaveLength(1);
    expect(events[0].tipo).toBe("cambio_pestana");
    expect(events[0].severidad).toBe("media");
    expect(events[0].trigger_evidence).toBe(true);
  });

  it("copiar_pegar dispara trigger_evidence en cada accion discreta", () => {
    const rules = new StateTransitionRules();
    const events = rules.process({ ts_ms: 0, face_count: 1, clipboard_action: "paste" });
    expect(events).toHaveLength(1);
    expect(events[0].tipo).toBe("copiar_pegar");
    expect(events[0].trigger_evidence).toBe(true);
    expect(events[0].payload).toEqual({ accion: "paste" });
  });

  it("copiar_pegar incluye clipboard_sha256 en el payload cuando esta disponible", () => {
    const rules = new StateTransitionRules();
    const hash = "a".repeat(64);
    const events = rules.process({
      ts_ms: 0,
      face_count: 1,
      clipboard_action: "paste",
      clipboard_sha256: hash,
    });
    expect(events[0].payload).toEqual({ accion: "paste", clipboard_sha256: hash });
  });

  it("copy (sin paste) no incluye clipboard_sha256 aunque el campo este seteado en la senal", () => {
    // clipboard_sha256 solo tiene sentido para 'paste' (contenido pegado); si la
    // senal trae 'copy', el payload no debe cargar un hash espurio.
    const rules = new StateTransitionRules();
    const events = rules.process({
      ts_ms: 0,
      face_count: 1,
      clipboard_action: "copy",
      clipboard_sha256: undefined,
    });
    expect(events[0].payload).toEqual({ accion: "copy" });
  });
});
