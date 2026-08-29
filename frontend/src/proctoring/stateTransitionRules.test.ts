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

/**
 * La pantalla es un RECTANGULO, no un punto. Medir la desviacion como un radio
 * (`hypot(x, y)` contra un unico umbral) trata igual dos cosas que no lo son:
 * mirar a un costado (fuera del monitor, es lo que interesa) y mirar el borde de
 * abajo del enunciado (adentro del monitor, es leer). Leer un enunciado largo abajo
 * dura mas que los 2,5 s del umbral sostenido, asi que el falso positivo era
 * alcanzable con solo rendir normalmente, y peor cuanto mas grande el monitor.
 *
 * Encima el eje vertical es la senal mas sucia que produce el motor: en
 * `gazeFromIris` el desplazamiento vertical se normaliza por el SEMI-ANCHO del ojo
 * (no por su altura), y arrastra el parpado que tapa el iris al mirar abajo. Aporta
 * poco y ensucia mucho, pero sumaba igual a la magnitud.
 */
describe("mirar arriba y abajo dentro de la pantalla no es mirada desviada", () => {
  it("leer sostenido el borde inferior de la pantalla no genera evento", () => {
    const rules = new StateTransitionRules();
    // Desvio puramente vertical, del tamano del que produce recorrer la pantalla
    // con la vista. Con el umbral radial de 0.20 esto disparaba.
    rules.process({ ts_ms: 0, face_count: 1, gaze: { x: 0.0, y: 0.3 } });
    rules.process({ ts_ms: 2000, face_count: 1, gaze: { x: 0.02, y: 0.31 } });
    const events = rules.process({ ts_ms: 4500, face_count: 1, gaze: { x: 0.01, y: 0.29 } });
    expect(events).toHaveLength(0);
  });

  it("mirar abajo MUCHO (apuntes sobre el escritorio) sigue generando evento", () => {
    const rules = new StateTransitionRules();
    // El escritorio esta a un angulo muy distinto del borde de la pantalla: aflojar
    // el eje vertical no puede volverse una via libre para leer apuntes.
    rules.process({ ts_ms: 0, face_count: 1, gaze: { x: 0.0, y: 0.7 } });
    rules.process({ ts_ms: 2000, face_count: 1, gaze: { x: 0.01, y: 0.71 } });
    const events = rules.process({ ts_ms: 4500, face_count: 1, gaze: { x: 0.0, y: 0.69 } });
    expect(events).toHaveLength(1);
    expect(events[0].tipo).toBe("mirada_desviada_sostenida");
  });

  it("el eje horizontal conserva su sensibilidad: mirar al costado dispara igual", () => {
    const rules = new StateTransitionRules();
    // Apenas por encima del umbral horizontal (0.20) y sin nada de vertical: es el
    // caso que el sistema TIENE que seguir viendo (otra pantalla, alguien al lado).
    rules.process({ ts_ms: 0, face_count: 1, gaze: { x: 0.25, y: 0.0 } });
    rules.process({ ts_ms: 2000, face_count: 1, gaze: { x: 0.26, y: 0.01 } });
    const events = rules.process({ ts_ms: 4500, face_count: 1, gaze: { x: 0.24, y: 0.0 } });
    expect(events).toHaveLength(1);
    expect(events[0].tipo).toBe("mirada_desviada_sostenida");
  });

  it("un vertical grande ya no empuja a un horizontal chico por encima del umbral", () => {
    const rules = new StateTransitionRules();
    // hypot(0.15, 0.35) = 0.38, muy por encima de 0.20: con el radio unico esto
    // disparaba, y es alguien leyendo la parte de abajo de su pantalla ancha.
    rules.process({ ts_ms: 0, face_count: 1, gaze: { x: 0.15, y: 0.35 } });
    rules.process({ ts_ms: 2000, face_count: 1, gaze: { x: 0.16, y: 0.34 } });
    const events = rules.process({ ts_ms: 4500, face_count: 1, gaze: { x: 0.15, y: 0.36 } });
    expect(events).toHaveLength(0);
  });

  it("la tolerancia vertical acompana al umbral configurado por la institucion", () => {
    // Sensibilidad alta (umbral 0.10): el mismo desvio vertical que se tolera con
    // el default ahora si dispara. El vertical no es un numero suelto, escala con
    // el unico control que la institucion mueve.
    const rules = new StateTransitionRules({ gaze_deviation_threshold: 0.10 });
    rules.process({ ts_ms: 0, face_count: 1, gaze: { x: 0.0, y: 0.3 } });
    rules.process({ ts_ms: 2000, face_count: 1, gaze: { x: 0.0, y: 0.31 } });
    const events = rules.process({ ts_ms: 4500, face_count: 1, gaze: { x: 0.0, y: 0.29 } });
    expect(events).toHaveLength(1);
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

describe("calibracion de baseline de mirada (camara fisicamente descentrada)", () => {
  it("sin calibrar, una camara descentrada genera un vector de iris con magnitud alta y dispara falso positivo", () => {
    const rules = new StateTransitionRules();
    rules.process({ ts_ms: 0, face_count: 1, gaze: { x: 0.3, y: 0 } });
    rules.process({ ts_ms: 2000, face_count: 1, gaze: { x: 0.3, y: 0 } });
    const events = rules.process({ ts_ms: 4500, face_count: 1, gaze: { x: 0.3, y: 0 } });
    expect(events).toHaveLength(1);
    expect(events[0].tipo).toBe("mirada_desviada_sostenida");
  });

  it("calibrando ese mismo punto como baseline, mirar ahi normalmente ya NO dispara evento", () => {
    const rules = new StateTransitionRules();
    rules.calibrarGaze({ x: 0.3, y: 0 });
    rules.process({ ts_ms: 0, face_count: 1, gaze: { x: 0.3, y: 0 } });
    rules.process({ ts_ms: 2000, face_count: 1, gaze: { x: 0.3, y: 0 } });
    const events = rules.process({ ts_ms: 4500, face_count: 1, gaze: { x: 0.3, y: 0 } });
    expect(events).toHaveLength(0);
  });

  it("calibrado, una desviacion REAL mas alla del baseline sigue disparando evento", () => {
    const rules = new StateTransitionRules();
    rules.calibrarGaze({ x: 0.3, y: 0 });
    // 0.6 absoluto = 0.3 (baseline) + 0.3 (desvio real) -> relativo 0.3 > threshold 0.20
    rules.process({ ts_ms: 0, face_count: 1, gaze: { x: 0.6, y: 0 } });
    rules.process({ ts_ms: 2000, face_count: 1, gaze: { x: 0.6, y: 0 } });
    const events = rules.process({ ts_ms: 4500, face_count: 1, gaze: { x: 0.6, y: 0 } });
    expect(events).toHaveLength(1);
    expect(events[0].tipo).toBe("mirada_desviada_sostenida");
  });

  it("el payload del evento reporta el gaze crudo (absoluto), no el relativo al baseline", () => {
    const rules = new StateTransitionRules();
    rules.calibrarGaze({ x: 0.3, y: 0 });
    rules.process({ ts_ms: 0, face_count: 1, gaze: { x: 0.6, y: 0 } });
    rules.process({ ts_ms: 2000, face_count: 1, gaze: { x: 0.6, y: 0 } });
    const events = rules.process({ ts_ms: 4500, face_count: 1, gaze: { x: 0.6, y: 0 } });
    expect(events[0].payload.gaze).toEqual({ x: 0.6, y: 0 });
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
