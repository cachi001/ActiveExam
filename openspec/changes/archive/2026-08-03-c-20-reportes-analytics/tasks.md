# Tasks — C-20 `reportes-analytics` (estadísticas standalone, sin dependencias)

> **REVISIÓN (2026-07-19)**: C-20 se DESACOPLA de C-13/C-16. Ya no espera los
> continuous aggregates ni las decisiones humanas: computa las **métricas sobre los
> datos que YA existen** (exam_content, materia, comisión, proctoring_session,
> proctoring_event + scoring config). Es un **informe/dashboard de métricas reales**
> (cantidad de exámenes/materias/comisiones/sesiones, personas en riesgo, distribución
> de scores), que reemplaza la página vieja hardcodeada.
>
> **RECONCILIACIÓN (2026-07-21)**: se cruzó el `tasks.md` contra el código y los tests
> reales. Se marcaron las tareas que ya estaban hechas y probadas (estaban sin marcar),
> se dejaron como deuda EXPLÍCITA las que están implementadas pero SIN su test de "Done",
> y se agregó el alcance que se construyó de más y no figuraba (sección 7: exports +
> agregaciones extra + auditoría). **El export CSV se descartó por decisión del owner
> (2026-07-21)** — quedan PDF y Excel.
>
> **Principios inviolables (se mantienen)**: los reportes INFORMAN y AGREGAN, nunca
> emiten veredicto/acción (RN-SC-01, DD-01, L2.5). "Persona en riesgo" = score por
> encima del umbral = **señal de priorización para revisión humana, NO acusación**.
> PII minimizada: agregado por defecto (Ley 25.326). El Done de cada tarea es un test verde.

## 1. Capa de métricas agregadas sobre datos existentes (backend, sin C-13/C-16)

- [x] 1.1 Servicio de agregación que lee SOLO tablas ya existentes (exam_content, materia,
      comisión, proctoring_session, proctoring_event) — sin depender de continuous
      aggregates de TimescaleDB ni de decisiones de C-16; Done: test de conteos sobre DB real.
      HECHO: `resumen_service.obtener_resumen` + `test_resumen_conteos_y_riesgo` (DB real).
- [x] 1.2 **Conteos globales**: cantidad de exámenes (exam_content), materias, comisiones,
      sesiones totales y por estado terminal (activa/finalizada/anulada); Done: test de cada conteo.
      HECHO: `test_resumen_conteos_y_riesgo` (asserts de materias/comisiones/exámenes/sesiones/finalizadas).
- [x] 1.3 **Score por sesión on-demand**: reutilizar `calcular_score` (eventos + pesos de
      scoring config) para derivar el score de cada sesión sin tabla nueva; Done: test de score agregado.
      HECHO: score 50≥40 probado vía `sesiones_en_riesgo` y la distribución.
- [x] 1.4 La capa de métricas **no muta** nada (solo lee); Done: test de invariancia.
      HECHO: `test_capa_no_muta_nada_invariancia` (snapshot de conteos antes/después de
      `obtener_resumen` — iguales).

## 2. Métricas de riesgo y distribución (capability `statistical-distribution-analytics`)

- [x] 2.1 **Personas/sesiones en riesgo**: sesiones con score ≥ umbral (de config), como
      CONTEO agregado y señal de priorización — nunca veredicto; Done: test de conteo de riesgo.
      HECHO: `test_resumen_conteos_y_riesgo` (`sesiones_en_riesgo == 1`).
- [x] 2.2 **Distribución de scores** (histograma/buckets) sobre las sesiones del
      período/examen; Done: test de distribución.
      HECHO: `test_resumen_distribucion_scores` (buckets 0-24/25-49/50-69/70-100).
      NOTA: percentiles NO implementados (solo buckets) — si se quieren, task nueva.
- [x] 2.3 Filtros del informe: por examen, por materia, por comisión, por rango de fechas;
      Done: test de agregación filtrada.
      HECHO: `test_filtro_por_materia_acota_sesiones`, `test_filtro_rango_fechas`,
      `test_filtro_materia_id_invalido_no_rompe` (materia + fechas probados; comisión/examen
      existen en `FiltrosStats` y se cablean en el endpoint, sin test dedicado propio).
- [x] 2.4 Contrato de salida: el "riesgo" es prioridad ordinal / señal, jamás culpa (RN-SC-01);
      Done: test de contrato (señal, no veredicto).
      HECHO: `test_contrato_riesgo_es_senal_no_veredicto` (riesgo = conteo int; el dataclass
      no tiene campos de veredicto/sanción).

## 3. Endpoint(s) + esquemas (capability `post-exam-reports`)

- [x] 3.1 Endpoint `GET /api/v1/stats/resumen` → sumario institucional (conteos + riesgo +
      distribución), RBAC (admin_sistema/coordinador); Done: test del endpoint (200 con rol, 403 sin rol).
      HECHO: `test_endpoint_resumen_admin_200` + `test_endpoint_resumen_estudiante_403`.
- [x] 3.2 Schemas Pydantic con `extra='forbid'`; agregado SIN PII por defecto (nombres solo
      con permiso + audit); Done: test de ausencia de PII en el agregado.
      HECHO: `test_endpoint_resumen_sin_pii_y_forbid` (schema `extra='forbid'` + sin emails ni
      claves de PII en el agregado).
- [x] 3.3 Degradación segura: sin datos → ceros legítimos (no error); un fallo no rompe la
      página; Done: test de resultado vacío vs error.
      HECHO: `test_resumen_vacio_da_ceros`.

## 4. Página de estadísticas real (frontend, reemplaza la hardcodeada)

- [x] 4.1 N/A — no existía una página de estadísticas hardcodeada separada. El
      `AdminDashboard` ya consumía datos reales; las métricas nuevas (materias/
      comisiones/distribución) no se mostraban en ningún lado. Decisión del owner:
      página NUEVA dedicada `/admin/estadisticas`, dejando el Dashboard operativo intacto.
- [x] 4.2 Nueva página de estadísticas: stat cards (exámenes/materias/comisiones/sesiones/
      en riesgo) + gráfico de distribución de scores, consumiendo `/stats/resumen`. Done:
      `EstadisticasBody.test.tsx` (render con datos del endpoint, mock del fetch) +
      `apiStats.test.ts` (capa API, mock del fetch, no de la DB).
- [x] 4.3 Contrato de carga resiliente (C-73): cargando/error/vacío-real/cargado; un fetch
      fallido NO se muestra como "0". Done: `EstadisticasBody.test.tsx` (5 casos de estado,
      incluye "error nunca degrada a 0").
- [x] 4.4 Filtros en la UI (examen/materia/comisión/fechas) cableados al endpoint; Done: test de filtros.
      HECHO: `EstadisticasInstitucionales.filtros.test.tsx` (aplicar una materia re-pide el
      resumen con `{materia_id}`; sin cambios no aparece "Aplicar filtros"). 2 tests verdes.

## 5. Garantías transversales de gobernanza y privacidad

- [x] 5.1 Verificar que ningún path del informe emite sanción/veredicto/acción automática
      (RN-SC-01, RN-DSR-04, DD-01); Done: test de no-veredicto.
      HECHO: `test_endpoint_resumen_no_expone_veredicto` (ninguna clave de veredicto en la
      respuesta; riesgo = conteo int).
- [x] 5.2 Minimización de PII: agregado por defecto, nominal restringido + auditado
      (Ley 25.326); Done: test transversal de minimización.
      HECHO: `test_minimizacion_pii_en_desgloses` (por_materia/top_eventos/por_dia exponen solo
      id de catálogo + conteos, sin identidad individual).

## 6. Cierre

- [x] 6.1 `tsc --noEmit` frontend + suite backend (por-archivo) y frontend en verde.
      FRONTEND: HECHO (2026-07-21) — `tsc --noEmit` exit 0 + stats/auditoría 27 tests verdes
      (incluye el nuevo `EstadisticasInstitucionales.filtros.test.tsx`).
      BACKEND: HECHO (2026-07-21) — `tests/test_c20_stats_resumen.py` + `tests/test_c20_audit.py`
      = 25 passed (contra base `proctoring_test`, .venv con fpdf2/openpyxl instalados).
- [x] 6.2 `openspec validate c-20-reportes-analytics` en verde. HECHO (2026-07-21).

## 7. Alcance entregado FUERA del plan original (reconciliación 2026-07-21)

> Todo esto se construyó en las sesiones en vivo, tiene test verde, y NO figuraba
> como task. Se documenta acá para no perder el rastro.

- [x] 7.1 **Agregaciones extra** por materia / top de eventos / por día / decisiones,
      con filtros; Done: `test_por_materia_sin_filtro_lista_todas`, `test_top_eventos_ordena_por_frecuencia`,
      `test_por_dia_y_decisiones`, `test_endpoint_resumen_incluye_agregaciones_nuevas`.
- [x] 7.2 **Export PDF** del sumario (dashboard de gráficos matplotlib embebido); Done:
      `test_endpoint_export_pdf` (magic `%PDF` + `/Image`). `GET /api/v1/stats/export.pdf`.
- [x] 7.3 **Export Excel (.xlsx)** con hojas y gráficos nativos (openpyxl); Done:
      `test_endpoint_export_xlsx` (magic `PK` + hojas "Resumen"/"Por materia" + charts).
      `GET /api/v1/stats/export.xlsx`.
- [x] 7.4 **Auditoría — servicio**: registro append-only con cadena de hash SHA-256
      (trigger `audit_log_encadenar`), filtros por acción/actor y paginación; Done:
      `test_c20_audit.py` — `test_registrar_y_listar_mas_reciente_primero` (cadena_valida),
      `test_filtro_por_accion`, `test_filtro_por_actor`, `test_paginacion`.
- [x] 7.5 **Auditoría — endpoint** `GET /api/v1/admin/audit-log` con RBAC (admin_sistema);
      Done: `test_endpoint_audit_log_admin_200` (200 + cadena_valida) + `test_endpoint_audit_log_estudiante_403`.
- [x] 7.6 **Auditoría — frontend** `Auditoria.tsx` (avatar con ícono por acción, detalle
      de config legible, FiltrosPanel + Pagination); Done: `auditoria.helpers.test.ts`.

> **Diferido a Fase 2 (cuando existan C-13/C-16)** — NO bloquea este change:
> reportes nominales por estudiante con línea de tiempo, métricas de calidad del detector
> (falsos positivos leyendo decisiones humanas), export JSON y recalibración de umbrales.
> Se re-incorporan como tasks cuando el score final consolidado (C-13) y las decisiones
> humanas (C-16) estén disponibles.
