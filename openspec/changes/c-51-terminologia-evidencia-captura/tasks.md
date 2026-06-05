## 1. knowledge-base/03_actores_y_roles.md — clip → captura

- [x] 1.1 Línea ~28: en el párrafo introductorio de RBAC, reemplazar "La descarga de un clip requiere URL firmada que expira en 15 min" → "La descarga de una captura requiere URL firmada que expira en 15 min"
- [x] 1.2 Línea ~35: en la fila del Proctor de la matriz RBAC, reemplazar "R (clip vía URL firmada 15 min)" → "R (captura vía URL firmada 15 min)"

## 2. knowledge-base/08_arquitectura_propuesta.md — clip → captura

- [x] 2.1 Línea ~60 (sección Seguridad): reemplazar "Descarga de clips vía URL firmada (expira 15 min) con propósito declarado en audit log" → "Descarga de capturas vía URL firmada (expira 15 min) con propósito declarado en audit log"

## 3. knowledge-base/07_flujos_principales.md — clip → captura/screenshot + biometría

- [x] 3.1 Flujo 4 (diagrama de secuencia): reemplazar "── PUT clip ──" → "── PUT captura ──"
- [x] 3.2 Flujo 4 (diagrama de secuencia): reemplazar "│◄── GET clip ──" → "│◄── GET captura ──"
- [x] 3.3 Flujo 4 (Casos de error): reemplazar "el clip queda en buffer; reintento de subida" → "la captura queda en buffer; reintento de subida"
- [x] 3.4 Flujo 7 (Revisor — Contexto completo): reemplazar "clips firmados" → "capturas firmadas"
- [x] 3.5 Flujo 4 (Pasos detallados): reemplazar "(2) pide URL firmada y sube el clip directo al storage" → "(2) pide URL firmada y sube la captura directa al storage"
- [x] 3.6 Flujo 0 (vista general, línea [BIOMETRÍA]): reemplazar "Captura video 3-5s → liveness → embedding facial → comparación 1:1" → "Foto (snapshot) + liveness → embedding facial → comparación 1:1"
- [x] 3.7 Flujo 2 (diagrama de secuencia): reemplazar "captura video 3-5s" → "captura foto (snapshot)"
- [x] 3.8 Flujo 2 (Pasos — paso 2): reemplazar "Captura de video corto (3–5 s)." → "Captura de foto (snapshot)."

## 4. knowledge-base/14_observabilidad_y_devops.md — clip → captura

- [x] 4.1 Línea ~49 (tabla Runbooks): reemplazar "los clips quedan en buffer; reintentar subida" → "las capturas quedan en buffer; reintentar subida"

## 5. knowledge-base/10_preguntas_abiertas.md — clip → captura + nota DPIA

- [x] 5.1 Línea ~40 (tabla preguntas abiertas, fila retención): reemplazar "clips, embeddings, eventos" → "capturas, embeddings, eventos"
- [x] 5.2 Agregar al final del archivo la sección "## Cambios relevantes con impacto de gobernanza" con la nota de C-51 sobre el tradeoff de liveness temporal server-side y la obligación DPIA (ver design.md D-03)

## 6. knowledge-base/12_biometria_y_liveness.md — clip/video → foto + embedding

- [x] 6.1 Línea ~7 (paso 1 del flujo biométrico): reemplazar "**Captura**: video corto (3–5 s) con instrucciones claras." → "**Captura**: foto (snapshot) con instrucciones claras."
- [x] 6.2 Línea ~20 (sección Persistencia): reemplazar "Se persisten dos artefactos: el clip de verificación (misma cadena de custodia que cualquier evidencia) y el embedding (cifrado at-rest, para la verificación continua)." → "Se persisten dos artefactos: la foto de referencia (misma cadena de custodia que cualquier evidencia) y el embedding ..."

## 7. knowledge-base/06_funcionalidades.md — clip/video → foto + embedding

- [x] 7.1 Épica 4 / US-004 CA-1: reemplazar "Capturo un video corto (3–5 s) con instrucciones claras." → "Capturo una foto (snapshot) con instrucciones claras."
- [x] 7.2 Épica 4 / US-004 CA-6: reemplazar "El clip y el embedding se persisten con cadena de custodia." → "La foto y el embedding se persisten con cadena de custodia."
- [x] 7.3 Épica 8 / US-008 CA-1: reemplazar "Un evento severo dispara un clip de 5–10 s" → "Un evento severo dispara una captura (screenshot)"
- [x] 7.4 Épica 8 / US-008 CA-3: reemplazar "El clip de verificación biométrica" → "La foto de referencia biométrica"
- [x] 7.5 Épica 12 / US-012 CA-3: reemplazar "clips firmados" → "capturas firmadas"
- [x] 7.6 Épica 8 / US-008 descripción: reemplazar "capturar un clip ante eventos severos" → "capturar una captura (screenshot) ante eventos severos"

## 8. Archivos adicionales con referencias encontradas en barrido final

- [x] 8.1 knowledge-base/01_vision_y_objetivos.md: "captura de video corto → liveness" → "captura de foto (snapshot) → liveness"; "Captura de evidencia (clips)" → "Captura de evidencia (screenshots)"
- [x] 8.2 knowledge-base/02_descripcion_general.md: API table "URL firmada para subir un clip" → "URL firmada para subir una captura"
- [x] 8.3 knowledge-base/05_reglas_de_negocio.md: RN-BIO-01 "captura de video 3–5 s" → "captura de foto (snapshot)"; RN-BIO-07 "clip de verificación" → "foto de referencia (snapshot de enrollment)"; RN-CC-05 "descarga de un clip" → "descarga de una captura"
- [x] 8.4 knowledge-base/11_ia_y_vision.md: "re-ejecuta modelos sobre el clip" → "sobre la captura (frame estático — C-24, DD-24-03)"

## 9. Verificación final

- [x] 9.1 Confirmar que NO se modificó ningún archivo con extensión .py o .ts (cero archivos de código) — verificado con `git diff --name-only`: solo archivos .md en knowledge-base/
- [x] 9.2 Ejecutar `openspec validate --strict c-51-terminologia-evidencia-captura` — resultado: "Change 'c-51-terminologia-evidencia-captura' is valid"
