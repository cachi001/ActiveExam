// Prueba de carga contra el backend REAL desplegado (`main_activeexam`).
//
// Por qué existe: el único k6 que había (`poc/k6/students.js`) le pega a
// `/api/v1/events/ws` con un JWT de Keycloak, y eso es el backend del PoC C-03,
// que es OTRA arquitectura. El backend que corre en producción es
// `main_activeexam`, que usa REST y el JWT propio. La prueba de 150 a 1200
// alumnos del 21/8/2026 se corrió con algo que no quedó en el repo, así que no
// se podía repetir. Esto la hace repetible.
//
// Simula el camino caliente de una rendición:
//   1. POST /api/v1/proctoring/sessions            (crear sesión)
//   2. POST /api/v1/proctoring/sessions/{id}/events  (N eventos por minuto)
//   3. PATCH /api/v1/proctoring/sessions/{id}/finalizar
//
// Uso:
//   k6 run -e BASE=http://localhost:8000 -e USUARIO=estudiante1 -e PASSWORD=... \
//          -e VUS=200 -e DURACION=5m tools/carga/carga-activeexam.js
//
// ⚠️ NO correrlo contra producción sin avisar: escribe sesiones y eventos
// reales en la base. Las sesiones quedan en `modo: 'test'` justamente para que
// se puedan borrar después (DELETE /sessions/{id} es admin-only y solo acepta
// sesiones de test).

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

const BASE = __ENV.BASE || 'http://localhost:8000';
const USUARIO = __ENV.USUARIO || 'estudiante1';
const PASSWORD = __ENV.PASSWORD || 'Estudiante123';
const VUS = Number(__ENV.VUS || 50);
const DURACION = __ENV.DURACION || '2m';
// Eventos por minuto por alumno. El cliente real manda ~1 cada 1 a 5 s según
// lo que detecte; 20/min es un ritmo conservador y sostenido.
const EVENTOS_POR_MINUTO = Number(__ENV.EVENTOS_POR_MINUTO || 20);

// --- Los POLLERS del cliente real -------------------------------------------
//
// Sin esto la medicion no significa nada. Medido el 25/8/2026, el trafico
// dominante NO son los eventos: son los pollers. Con 100 alumnos el chat son
// ~29 req/s y las pausas otros tantos, sobre un techo de 80 req/s. Un harness
// que solo postea eventos da un numero comodo que no describe la realidad.
//
// Las cadencias espejan al cliente EXACTAMENTE:
//   - ChatBox      -> 15 s mientras nadie escribio (POLL_CHAT_INACTIVO_MS en
//     ui/chat/chatCadencia.ts), 3,5 s con la conversacion viva. El alumno virtual
//     no chatea, asi que se queda en reposo, que es el caso del 99% del examen.
//     Para medir el peor caso (todos conversando) correr con CHAT_POLL_MS=3500.
//   - PausaAlumno  -> 20 s en reposo (POLL_PAUSA_INACTIVO_MS). El alumno virtual
//     no pide pausas, asi que se queda en reposo, que es el caso del 99% del examen.
const CHAT = (__ENV.CHAT || 'true') !== 'false';
const PAUSAS = (__ENV.PAUSAS || 'true') !== 'false';
const CHAT_POLL_MS = Number(__ENV.CHAT_POLL_MS || 15000);
const PAUSA_POLL_MS = Number(__ENV.PAUSA_POLL_MS || 20000);

// Fraccion de eventos que llevan captura (0 a 1). APAGADO por defecto a
// proposito: una captura real pesa ~114 KB en base64 y la base del plan free
// son 1 GB. Prenderlo contra produccion la puede llenar — ver el README.
const CAPTURAS = Number(__ENV.CAPTURAS || 0);
// Captura sintetica del tamano real (960x540 JPEG ~85 KB -> ~114 KB en base64).
const CAPTURA_B64 = CAPTURAS > 0 ? 'A'.repeat(Number(__ENV.CAPTURA_BYTES || 114000)) : null;

// --- CAIDA DE CONEXION -------------------------------------------------------
//
// Lo que se mide no es "aguanta menos trafico" (es al reves: mientras esta
// caido no manda nada). Lo que se mide es el REGRESO: el cliente bufferea en
// IndexedDB y al volver la conexion drena TODO junto. Dos preguntas:
//
//   1. żse pierde evidencia? -> se cuenta lo enviado y se compara contra lo que
//      el servidor devuelve en GET /sessions/{id}. Es la unica verificacion que
//      importa: un examen sin su evidencia no sirve de nada.
//   2. żque le hace al resto la rafaga de vuelta? -> si se cae el wifi del aula,
//      no vuelve UN alumno: vuelven todos a la vez. Por eso la caida arranca a
//      la MISMA altura de la iteracion en todos los VUs afectados.
//
// CAIDA_SEG=0 lo apaga (default). CAIDA_PCT es que fraccion de alumnos se cae.
const CAIDA_SEG = Number(__ENV.CAIDA_SEG || 0);
const CAIDA_PCT = Number(__ENV.CAIDA_PCT || 1);
const CAIDA_EN_SEG = Number(__ENV.CAIDA_EN_SEG || 20);
// La verificación de "no se perdió evidencia" lee el DETALLE de la sesión, y ese
// endpoint es de SUPERVISIÓN: con el token del alumno da 403. Sin estas
// credenciales la caída se corre igual pero sin verificar nada — que es
// justamente lo que no queremos, así que el harness lo avisa por consola.
//
// Tiene que ser ADMIN, no coordinador: desde c-79 el coordinador está acotado a
// SUS materias, y estas sesiones son `modo: 'test'` (sin examen vinculado), así
// que la pertenencia no resuelve y devuelve 403 igual que el alumno.
const STAFF_USUARIO = __ENV.STAFF_USUARIO || 'admin';
const STAFF_PASSWORD = __ENV.STAFF_PASSWORD || 'Admin123';

// Severidades en FEMENINO. Escribirlas en masculino da score 0 en silencio
// (ver el comentario de `Severidad` en backend/app/domain/events/schema.py).
const SEVERIDADES = ['baja', 'media', 'alta'];
const TIPOS = ['FACE_ABSENT', 'MULTIPLE_FACES', 'GAZE_AWAY', 'TAB_HIDDEN'];

const latenciaCrearSesion = new Trend('ae_crear_sesion_ms', true);
const latenciaEvento = new Trend('ae_evento_ms', true);
const latenciaFinalizar = new Trend('ae_finalizar_ms', true);
const erroresIngesta = new Rate('ae_errores_ingesta');
const eventosEnviados = new Counter('ae_eventos_enviados');
const latenciaChat = new Trend('ae_chat_poll_ms', true);
const latenciaPausa = new Trend('ae_pausa_poll_ms', true);
const pollsChat = new Counter('ae_chat_polls');
const pollsPausa = new Counter('ae_pausa_polls');
// Caida de conexion: cuanto tarda el drenaje del buffer al volver, cuantos
// eventos trae, y —lo unico que de verdad importa— si se perdio evidencia.
const latenciaReplay = new Trend('ae_replay_ms', true);
const eventosReplay = new Counter('ae_replay_eventos');
const evidenciaPerdida = new Rate('ae_evidencia_perdida');

// El cliente real drena EN TANDAS desde c-78 §16.1f (un request por tanda, no
// uno por evento). El harness lo espeja: medirlo de a uno daria un numero que ya
// no describe lo que hace el navegador. LOTE=false vuelve al camino viejo, que
// es lo que permite comparar los dos.
const LOTE = (__ENV.LOTE || 'true') !== 'false';
const LOTE_TAMANO = Number(__ENV.LOTE_TAMANO || 50);

/**
 * Drena el buffer al reconectar y devuelve cuánto tardó, en ms.
 *
 * Espeja al cliente real: desde c-78 §16.1f manda TANDAS (un request por tanda)
 * en vez de un evento por request. De a uno, drenar una caída de 30 s tardaba
 * 35,6 s de media contra Render — el plan free responde a 3 a 5 s por request y
 * el drenaje los pagaba en serie.
 *
 * Con `LOTE=false` vuelve al camino de a uno, que es lo que permite comparar.
 */
function drenarBuffer(sesionId, pendientes, headers) {
  const arranque = Date.now();

  if (LOTE) {
    for (let i = 0; i < pendientes.length; i += LOTE_TAMANO) {
      const tanda = pendientes.slice(i, i + LOTE_TAMANO);
      const res = http.post(
        `${BASE}/api/v1/proctoring/sessions/${sesionId}/events/lote`,
        JSON.stringify({ eventos: tanda }),
        { headers, tags: { endpoint: 'replay_lote' } },
      );
      eventosReplay.add(tanda.length);
      erroresIngesta.add(!check(res, {
        'lote del buffer aceptado (201)': (r) => r.status === 201,
      }));
    }
    return Date.now() - arranque;
  }

  for (const pendiente of pendientes) {
    const res = http.post(
      `${BASE}/api/v1/proctoring/sessions/${sesionId}/events`,
      JSON.stringify(pendiente),
      { headers, tags: { endpoint: 'replay_evento' } },
    );
    eventosReplay.add(1);
    erroresIngesta.add(!check(res, {
      'evento del buffer aceptado (201)': (r) => r.status === 201,
    }));
  }
  return Date.now() - arranque;
}

export const options = {
  vus: VUS,
  duration: DURACION,
  thresholds: {
    // El SLO del proyecto para el fan-out es p99 < 500 ms. Acá medimos la
    // INGESTA, que es la parte que sostiene el pico de escritura.
    ae_evento_ms: ['p(95)<500', 'p(99)<1000'],
    ae_errores_ingesta: ['rate<0.01'],
    http_req_failed: ['rate<0.01'],
    // Cero. Perder evidencia no tiene umbral aceptable: un examen sin su
    // evidencia no sirve para nada.
    ae_evidencia_perdida: ['rate==0'],
  },
};

/**
 * Un solo login para toda la corrida. Si cada VU se logueara, estaríamos
 * midiendo bcrypt en vez de la ingesta: el hash de contraseña es caro a
 * propósito y dominaría el resultado.
 *
 * ⚠️ El access token vive 15 minutos. Para corridas más largas hay que
 * refrescarlo (POST /api/v1/auth/refresh) o la corrida se llena de 401.
 */
export function setup() {
  const res = http.post(
    `${BASE}/api/v1/auth/login`,
    JSON.stringify({ username: USUARIO, password: PASSWORD }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  if (res.status !== 200) {
    throw new Error(`login fallo: ${res.status} ${res.body}`);
  }

  // Token de supervisión, SOLO para verificar que no se perdió evidencia tras
  // una caída. No se usa para nada del camino del alumno.
  let tokenStaff = null;
  if (CAIDA_SEG > 0) {
    const staff = http.post(
      `${BASE}/api/v1/auth/login`,
      JSON.stringify({ username: STAFF_USUARIO, password: STAFF_PASSWORD }),
      { headers: { 'Content-Type': 'application/json' } },
    );
    if (staff.status === 200) {
      tokenStaff = staff.json('access_token');
    } else {
      console.warn(
        `login de staff (${STAFF_USUARIO}) fallo: ${staff.status}. La caida se ` +
        'corre igual, pero NO se va a poder verificar si se perdio evidencia.',
      );
    }
  }

  return { token: res.json('access_token'), tokenStaff };
}

export default function (data) {
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${data.token}`,
  };

  // 1. Crear la sesión. `modo: 'test'` evita el enforcement de ventana de
  //    rendición e intentos, y deja la sesión borrable después.
  const crear = http.post(
    `${BASE}/api/v1/proctoring/sessions`,
    JSON.stringify({ modo: 'test', etiqueta: `carga-k6-vu${__VU}` }),
    { headers, tags: { endpoint: 'crear_sesion' } },
  );
  latenciaCrearSesion.add(crear.timings.duration);
  const ok = check(crear, { 'sesion creada (201)': (r) => r.status === 201 });
  if (!ok) {
    erroresIngesta.add(1);
    sleep(1);
    return;
  }
  const sesionId = crear.json('id');

  // 2. La rendición: eventos + los DOS pollers, cada uno a su cadencia real.
  //
  // Un solo loop con un tick corto y un "próximo vencimiento" por tarea. Espeja
  // al navegador, que tiene tres `setInterval` corriendo en paralelo — no una
  // secuencia. Medir solo los eventos (como hacía este harness antes) deja
  // afuera el ~70% del tráfico.
  const intervaloEventoMs = (60 / EVENTOS_POR_MINUTO) * 1000;
  const inicio = Date.now();
  const hasta = inicio + 60 * 1000; // un minuto de rendición por iteración
  let proxEvento = Date.now();
  let proxChat = Date.now();
  let proxPausa = Date.now();

  // Caída de conexión: a este VU le toca o no, y si le toca es SIEMPRE a la
  // misma altura de la iteración — cuando se cae el wifi del aula no vuelve un
  // alumno, vuelven todos juntos, y esa ráfaga simultánea es el caso a medir.
  const seCae = CAIDA_SEG > 0 && (__VU % 100) < CAIDA_PCT * 100;
  const caeEn = inicio + CAIDA_EN_SEG * 1000;
  const vuelveEn = caeEn + CAIDA_SEG * 1000;
  // El buffer de IndexedDB del cliente, del lado del harness.
  const buffer = [];
  let drenado = false;
  // Todo lo que este alumno dio por generado. Es el número contra el que se
  // compara lo que quedó guardado en el servidor.
  let generados = 0;

  while (Date.now() < hasta) {
    const ahora = Date.now();
    const caido = seCae && ahora >= caeEn && ahora < vuelveEn;

    // Volvió la conexión: drenar TODO el buffer de una, en orden, como hace el
    // cliente real. Es acá donde el servidor recibe la ráfaga.
    if (seCae && !caido && !drenado && buffer.length > 0) {
      latenciaReplay.add(drenarBuffer(sesionId, buffer, headers));
      buffer.length = 0;
      drenado = true;
    }

    if (ahora >= proxEvento) {
      const evento = {
        tipo: TIPOS[Math.floor(Math.random() * TIPOS.length)],
        severidad: SEVERIDADES[Math.floor(Math.random() * SEVERIDADES.length)],
        ts_cliente: new Date().toISOString(),
        payload: { origen: 'k6', vu: __VU },
      };
      // La captura va en una FRACCIÓN de los eventos, igual que en el cliente:
      // solo los 7 tipos de `EVENTOS_CON_EVIDENCIA_VISUAL` la adjuntan.
      if (CAPTURA_B64 && Math.random() < CAPTURAS) {
        evento.screenshot_base64 = CAPTURA_B64;
      }
      generados++;
      proxEvento = ahora + intervaloEventoMs;

      if (caido) {
        // Sin red no se manda: se guarda, igual que el cliente. El `ts_cliente`
        // queda con la hora en que PASÓ, no con la del reenvío.
        buffer.push(evento);
        continue;
      }

      const res = http.post(
        `${BASE}/api/v1/proctoring/sessions/${sesionId}/events`,
        JSON.stringify(evento),
        { headers, tags: { endpoint: 'ingesta_evento' } },
      );
      latenciaEvento.add(res.timings.duration);
      eventosEnviados.add(1);
      const aceptado = check(res, {
        'evento aceptado (201)': (r) => r.status === 201,
      });
      erroresIngesta.add(!aceptado);
    }

    // Mientras está caído tampoco pollea: no hay red. Saltear los pollers acá
    // es lo que hace que la caída se note como un hueco de tráfico y no como
    // un alumno que sigue conversando con el servidor sin conexión.
    if (caido) {
      sleep(0.1);
      continue;
    }

    if (CHAT && ahora >= proxChat) {
      const res = http.get(
        `${BASE}/api/v1/proctoring/sessions/${sesionId}/chat`,
        { headers, tags: { endpoint: 'poll_chat' } },
      );
      latenciaChat.add(res.timings.duration);
      pollsChat.add(1);
      check(res, { 'chat responde (200)': (r) => r.status === 200 });
      proxChat = ahora + CHAT_POLL_MS;
    }

    if (PAUSAS && ahora >= proxPausa) {
      const res = http.get(
        `${BASE}/api/v1/proctoring/sessions/${sesionId}/pausas`,
        { headers, tags: { endpoint: 'poll_pausas' } },
      );
      latenciaPausa.add(res.timings.duration);
      pollsPausa.add(1);
      check(res, { 'pausas responde (200)': (r) => r.status === 200 });
      proxPausa = ahora + PAUSA_POLL_MS;
    }

    sleep(0.1); // tick del loop; las cadencias las fijan los vencimientos
  }

  // Si la conexión no volvió antes de que terminara el examen, el cliente drena
  // igual al reconectar. No drenarlo acá haría que el harness "pierda" eventos
  // por su cuenta y ensuciaría justamente la métrica que queremos medir.
  if (buffer.length > 0) {
    latenciaReplay.add(drenarBuffer(sesionId, buffer, headers));
    buffer.length = 0;
  }

  // 3. Finalizar (idempotente).
  const fin = http.patch(
    `${BASE}/api/v1/proctoring/sessions/${sesionId}/finalizar`,
    null,
    { headers, tags: { endpoint: 'finalizar' } },
  );
  latenciaFinalizar.add(fin.timings.duration);
  check(fin, { 'sesion finalizada (200)': (r) => r.status === 200 });

  // 4. La verificación que importa: ¿quedó guardado TODO lo que pasó?
  //
  // Sin esto la prueba de caída no prueba nada: mediría que el servidor
  // respondió rápido mientras perdía evidencia en silencio. Se hace solo en el
  // escenario de caída — con 100 VUs, un GET del detalle completo por iteración
  // sería carga sintética que el cliente real no genera.
  if (seCae && data.tokenStaff) {
    const detalle = http.get(`${BASE}/api/v1/proctoring/sessions/${sesionId}`, {
      headers: { Authorization: `Bearer ${data.tokenStaff}` },
      tags: { endpoint: 'verificar_evidencia' },
    });
    if (detalle.status === 200) {
      const guardados = (detalle.json('eventos') || []).length;
      const completo = guardados >= generados;
      evidenciaPerdida.add(!completo);
      check(detalle, {
        'no se perdió evidencia tras la caída': () => completo,
      });
    } else {
      // No poder verificar NO es lo mismo que haber perdido evidencia, pero
      // tampoco se puede dar por buena una corrida sin verificar.
      console.warn(`no se pudo verificar la sesion ${sesionId}: HTTP ${detalle.status}`);
      evidenciaPerdida.add(true);
    }
  }
}
