# Tasks — C-20 `reportes-analytics` (estadísticas standalone, sin dependencias)

> **REVISIÓN (2026-07-19)**: C-20 se DESACOPLA de C-13/C-16. Ya no espera los
> continuous aggregates ni las decisiones humanas: computa las **métricas sobre los
> datos que YA existen** (exam_content, materia, comisión, proctoring_session,
> proctoring_event + scoring config). Es un **informe/dashboard de métricas reales**
> (cantidad de exámenes/materias/comisiones/sesiones, personas en riesgo, distribución
> de scores), que reemplaza la página vieja hardcodeada.
>
> **Principios inviolables (se mantienen)**: los reportes INFORMAN y AGREGAN, nunca
> emiten veredicto/acción (RN-SC-01, DD-01, L2.5). "Persona en riesgo" = score por
> encima del umbral = **señal de priorización para revisión humana, NO acusación**.
> PII minimizada: agregado por defecto (Ley 25.326). El Done de cada tarea es un test verde.

## 1. Capa de métricas agregadas sobre datos existentes (backend, sin C-13/C-16)

- [ ] 1.1 Servicio de agregación que lee SOLO tablas ya existentes (exam_content, materia,
      comisión, proctoring_session, proctoring_event) — sin depender de continuous
      aggregates de TimescaleDB ni de decisiones de C-16; Done: test de conteos sobre DB real
- [ ] 1.2 **Conteos globales**: cantidad de exámenes (exam_content), materias, comisiones,
      sesiones totales y por estado terminal (activa/finalizada/anulada); Done: test de cada conteo
- [ ] 1.3 **Score por sesión on-demand**: reutilizar `calcular_score` (eventos + pesos de
      scoring config) para derivar el score de cada sesión sin tabla nueva; Done: test de score agregado
- [ ] 1.4 La capa de métricas **no muta** nada (solo lee); Done: test de invariancia

## 2. Métricas de riesgo y distribución (capability `statistical-distribution-analytics`)

- [ ] 2.1 **Personas/sesiones en riesgo**: sesiones con score ≥ umbral (de config), como
      CONTEO agregado y señal de priorización — nunca veredicto; Done: test de conteo de riesgo
- [ ] 2.2 **Distribución de scores** (histograma/buckets + percentiles) sobre las sesiones
      del período/examen; Done: test de distribución
- [ ] 2.3 Filtros del informe: por examen, por materia, por comisión, por rango de fechas;
      Done: test de agregación filtrada
- [ ] 2.4 Contrato de salida: el "riesgo" es prioridad ordinal / señal, jamás culpa (RN-SC-01);
      Done: test de contrato (señal, no veredicto)

## 3. Endpoint(s) + esquemas (capability `post-exam-reports`)

- [ ] 3.1 Endpoint `GET /api/v1/stats/resumen` → sumario institucional (conteos + riesgo +
      distribución), RBAC (admin_sistema/coordinador); Done: test del endpoint (200 con rol, 403 sin rol)
- [ ] 3.2 Schemas Pydantic con `extra='forbid'`; agregado SIN PII por defecto (nombres solo
      con permiso + audit); Done: test de ausencia de PII en el agregado
- [ ] 3.3 Degradación segura: sin datos → ceros legítimos (no error); un fallo no rompe la
      página; Done: test de resultado vacío vs error

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
- [ ] 4.4 Filtros en la UI (examen/materia/comisión/fechas) cableados al endpoint; Done: test de filtros

## 5. Garantías transversales de gobernanza y privacidad

- [ ] 5.1 Verificar que ningún path del informe emite sanción/veredicto/acción automática
      (RN-SC-01, RN-DSR-04, DD-01); Done: test de no-veredicto
- [ ] 5.2 Minimización de PII: agregado por defecto, nominal restringido + auditado
      (Ley 25.326); Done: test transversal de minimización

## 6. Cierre

- [ ] 6.1 `tsc --noEmit` frontend + suite backend (por-archivo) y frontend en verde
- [ ] 6.2 `openspec validate c-20-reportes-analytics` en verde

> **Diferido a Fase 2 (cuando existan C-13/C-16)** — NO bloquea este change:
> reportes nominales por estudiante con línea de tiempo, métricas de calidad del detector
> (falsos positivos leyendo decisiones humanas), exports CSV/JSON y recalibración de umbrales.
> Se re-incorporan como tasks cuando el score final consolidado (C-13) y las decisiones
> humanas (C-16) estén disponibles.
