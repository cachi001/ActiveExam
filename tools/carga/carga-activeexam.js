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

// Severidades en FEMENINO. Escribirlas en masculino da score 0 en silencio
// (ver el comentario de `Severidad` en backend/app/domain/events/schema.py).
const SEVERIDADES = ['baja', 'media', 'alta'];
const TIPOS = ['FACE_ABSENT', 'MULTIPLE_FACES', 'GAZE_AWAY', 'TAB_HIDDEN'];

const latenciaCrearSesion = new Trend('ae_crear_sesion_ms', true);
const latenciaEvento = new Trend('ae_evento_ms', true);
const latenciaFinalizar = new Trend('ae_finalizar_ms', true);
const erroresIngesta = new Rate('ae_errores_ingesta');
const eventosEnviados = new Counter('ae_eventos_enviados');

export const options = {
  vus: VUS,
  duration: DURACION,
  thresholds: {
    // El SLO del proyecto para el fan-out es p99 < 500 ms. Acá medimos la
    // INGESTA, que es la parte que sostiene el pico de escritura.
    ae_evento_ms: ['p(95)<500', 'p(99)<1000'],
    ae_errores_ingesta: ['rate<0.01'],
    http_req_failed: ['rate<0.01'],
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
  return { token: res.json('access_token') };
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

  // 2. Stream de eventos al ritmo configurado, durante la vida del VU.
  const intervalo = 60 / EVENTOS_POR_MINUTO;
  const hasta = Date.now() + 60 * 1000; // un minuto de rendición por iteración
  while (Date.now() < hasta) {
    const evento = {
      tipo: TIPOS[Math.floor(Math.random() * TIPOS.length)],
      severidad: SEVERIDADES[Math.floor(Math.random() * SEVERIDADES.length)],
      ts_cliente: new Date().toISOString(),
      payload: { origen: 'k6', vu: __VU },
    };
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
    sleep(intervalo);
  }

  // 3. Finalizar (idempotente).
  const fin = http.patch(
    `${BASE}/api/v1/proctoring/sessions/${sesionId}/finalizar`,
    null,
    { headers, tags: { endpoint: 'finalizar' } },
  );
  latenciaFinalizar.add(fin.timings.duration);
  check(fin, { 'sesion finalizada (200)': (r) => r.status === 200 });
}
