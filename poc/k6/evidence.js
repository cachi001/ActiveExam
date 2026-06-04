// VU de evidencia para el harness de carga PoC C-03 (Bloque 4, DESCARTABLE).
//
// Genera carga sobre la cola Postgres (concern a): cada iteración encola UN job de
// evidencia sintética vía POST /poc/enqueue (endpoint PoC descartable que inserta en
// poc_job_queue). El worker poc_load_worker --forever la drena, midiendo
// evidence_signing_seconds (latencia de firma stub) y job_queue_depth (profundidad).
//
// DECISIÓN DE DISEÑO: NO se usa el endpoint real /api/v1/evidence/notify (que
// re-descarga el binario de WORM/MinIO + valida firma antes de encolar, flujo pesado
// y acoplado a la cola de prod). /poc/enqueue aísla la medición de la cola.
//
// USO (k6 debe estar instalado; el barrido real es Bloque 5):
//   # arrancar el worker en otra terminal:
//   docker exec proctoring-api-1 python -m app.workers.poc_load_worker --forever
//   # generar carga de encolado:
//   k6 run --vus 50 --duration 60s -e BASE_URL=http://localhost:8000 poc/k6/evidence.js
//
// Este script es DESCARTABLE.

import http from 'k6/http';
import { check } from 'k6';
import { Counter, Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const BLOB_SIZE = parseInt(__ENV.BLOB_SIZE || '1024', 10);

const encoladas = new Counter('poc_evidencias_encoladas');
const encolado_ok = new Rate('poc_encolado_ok');

export default function () {
  const body = JSON.stringify({ session_id: `vu-${__VU}`, blob_size: BLOB_SIZE });
  const res = http.post(`${BASE_URL}/poc/enqueue`, body, {
    headers: { 'Content-Type': 'application/json' },
  });
  const ok = res.status === 200;
  encolado_ok.add(ok);
  if (ok) {
    encoladas.add(1);
  }
  check(res, { 'encolada (200)': () => ok });
}
