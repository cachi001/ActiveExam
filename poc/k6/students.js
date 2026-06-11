// VU de estudiante para el harness de carga PoC C-03 (Bloque 4, DESCARTABLE).
//
// Cada VU abre un WebSocket /api/v1/events/ws con una sesión sembrada (seed.py),
// manda un heartbeat firmado HMAC cada 5 s + eventos normales, y mide la tasa de ack.
// El objetivo es generar ~200 inserts/s @ 100 VU para el barrido del concern (c).
//
// FIRMA (debe coincidir con el backend, signature.py + custody.py):
//   canonical = id|session_id|exam_id|tipo|severidad|ts_client|schema_version  (sep '|')
//   firma     = HMAC_SHA256(key=clave_sesion, msg=canonical)  -> hex
//
// JWT PoC HS256 (bypass Keycloak): firmado con POC_JWT_SECRET; claims aud/iss/exp.
//
// USO (k6 debe estar instalado; el barrido real es Bloque 5):
//   docker exec proctoring-api-1 python /tmp/seed.py --sessions 100 > poc/k6/sessions.json
//   k6 run --vus 100 --duration 60s \
//     -e POC_JWT_SECRET=poc-secret-k6-do-not-use-in-prod \
//     -e BASE_WS=ws://localhost:8000 poc/k6/students.js
//
// Este script es DESCARTABLE.

import ws from 'k6/ws';
import crypto from 'k6/crypto';
import encoding from 'k6/encoding';
import { check } from 'k6';
import { Counter, Rate } from 'k6/metrics';

// Sesiones sembradas por seed.py (cargadas una vez en el init context).
const SESSIONS = JSON.parse(open('./sessions.json'));

const SECRET = __ENV.POC_JWT_SECRET || 'poc-secret-k6-do-not-use-in-prod';
const BASE_WS = __ENV.BASE_WS || 'ws://localhost:8000';
const AUD = __ENV.JWT_AUDIENCE || 'proctoring-api';
const ISS = __ENV.JWT_ISSUER || 'http://keycloak:8080/realms/proctoring';
const DURATION_MS = parseInt(__ENV.VU_DURATION_MS || '55000', 10);
const HEARTBEAT_MS = 5000;

const eventos_enviados = new Counter('poc_eventos_enviados');
const ack_rate = new Rate('poc_ack_ok');

function b64url(obj) {
  return encoding.b64encode(JSON.stringify(obj), 'rawurl');
}

// JWT HS256 estático: el backend recomputa HMAC sobre 'header.payload' y compara.
function makeJWT() {
  const header = b64url({ alg: 'HS256', typ: 'JWT', kid: 'test-key' });
  const now = Math.floor(Date.now() / 1000);
  const payload = b64url({ sub: 'poc-load', aud: AUD, iss: ISS, exp: now + 3600, iat: now });
  const signingInput = `${header}.${payload}`;
  const sig = crypto.hmac('sha256', SECRET, signingInput, 'base64rawurl');
  return `${signingInput}.${sig}`;
}

// uuid v4 simple para el id del evento (no necesita ser criptográfico).
function uuid4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function firmarEvento(claveSesion, ev) {
  const canonical = [
    ev.id, ev.session_id, ev.exam_id, ev.tipo, ev.severidad, ev.ts_client,
    String(ev.schema_version),
  ].join('|');
  return crypto.hmac('sha256', claveSesion, canonical, 'hex');
}

function construirEvento(sesion, tipo, severidad) {
  const ev = {
    id: uuid4(),
    session_id: sesion.session_id,
    exam_id: sesion.exam_id,
    tipo: tipo,
    severidad: severidad,
    ts_client: new Date().toISOString(),
    payload: {},
    schema_version: 1,
  };
  ev.firma = firmarEvento(sesion.clave_sesion, ev);
  return ev;
}

export default function () {
  // Cada VU usa una sesión distinta (round-robin por índice de VU).
  const sesion = SESSIONS[(__VU - 1) % SESSIONS.length];
  const jwt = makeJWT();
  const url = `${BASE_WS}/api/v1/events/ws?session_id=${sesion.session_id}&access_token=${jwt}`;

  ws.connect(url, {}, function (socket) {
    socket.on('open', function () {
      // Heartbeat firmado cada 5 s (prueba de vida, ~200 inserts/s @ 100 VU con eventos).
      socket.setInterval(function () {
        const hb = construirEvento(sesion, 'heartbeat', 'baseline');
        socket.send(JSON.stringify(hb));
        eventos_enviados.add(1);
      }, HEARTBEAT_MS);

      // Evento normal cada 1 s (telemetría de mirada/postura — carga de fan-out).
      socket.setInterval(function () {
        const ev = construirEvento(sesion, 'mirada_desviada', 'media');
        socket.send(JSON.stringify(ev));
        eventos_enviados.add(1);
      }, 1000);

      socket.setTimeout(function () {
        socket.close();
      }, DURATION_MS);
    });

    socket.on('message', function (raw) {
      const msg = JSON.parse(raw);
      const ok = msg.persistido === true || msg.prueba_de_vida === true;
      ack_rate.add(ok);
      check(msg, { 'ack persistido/vivo': () => ok });
    });

    socket.on('error', function (e) {
      ack_rate.add(false);
    });
  });
}
