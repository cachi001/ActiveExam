## Why

Las pantallas del área admin/staff (AdminDashboard, ExamList, Reports, Revisor, SessionDetail, Proctor, AuditPrivacy) son funcionalmente correctas pero inconsistentes en densidad visual, tienen controles hardcodeados (umbral sin `RangeInput`, retos sin `FormField`) y dos pantallas monolíticas (Proctor ~150 líneas, Revisor ~195 líneas) mezclan layout, estado y sub-UI sin extraer componentes reutilizables. C-40 limpió la base, C-41/C-42 completaron el portal del alumno: es el momento natural de aplicar el mismo patrón al área admin.

## What Changes

- **AdminDashboard**: usar `SectionTitle` en "Acciones rápidas"; botones `size="sm"` en acciones rápidas (proporcionales al espacio); tabla de exámenes con jerarquía visual clara (sin texto apretado).
- **ExamList**: botón "Configurar" inline usar `Button size="sm"` en vez de un `<button>` custom con clases manuales; buscar input usa diseño consistente con el design system.
- **Reports**: barra de distribución de severidad usa `ProgressBar` (ya existe); leyenda del gráfico semanal más legible; carta de insight más compacta.
- **Revisor**: extraer `ReviewQueueItem` (ítem de la cola) y `ReviewDecisionPanel` (panel de resolución con botones y enlace a detalle); bajar densidad de la cola — espaciado más generoso entre ítems; tabla de anomalías usa `SectionTitle` con sub; re-usar `CadenaPaso` de SessionDetail.
- **SessionDetail**: sin grandes cambios estructurales — ya tiene `CadenaPaso` extraída y es el patrón a seguir; mejoras menores de consistencia visual (SectionTitle en encabezados).
- **Proctor**: extraer `StudentFeedCard` (video + overlay de nombre/score/señal) y `ProctorControls` (umbral + retos + mensaje correctivo); reemplazar `<input type="range">` raw por `RangeInput`; reemplazar `<h3>` sueltos por `SectionTitle`.
- **AuditPrivacy**: `AuditLogItem` (ítem de audit) extraído; derechos del titular como `DsrCard` genérico; `SectionTitle` en encabezados.
- **Datos mock**: verificar coherencia — Stat "Examen activo" en Proctor hardcodeada "Anatomía I" es aceptable como dato de demo activo real; audit log en AuditPrivacy usa fechas y actores reales del proyecto.

## Capabilities

### New Capabilities

- `admin-dashboard-ui`: Encabezado unificado AdminDashboard con acciones rápidas proporcionales y tabla de exámenes con jerarquía visual clara.
- `proctor-live-panel`: Componentes `StudentFeedCard` y `ProctorControls` extraídos de Proctor.tsx; uso de `RangeInput` y `SectionTitle`.
- `reviewer-queue-panel`: Componentes `ReviewQueueItem` y `ReviewDecisionPanel` extraídos de Revisor.tsx; densidad reducida.
- `audit-privacy-ui`: Componentes `AuditLogItem` y `DsrCard` extraídos de AuditPrivacy.tsx; `SectionTitle` consistente.

### Modified Capabilities

- `student-profile-shell`: Delta — SessionDetail.tsx usa `SectionTitle` en "Eventos discretos" para consistencia (cambio menor de requisito visual).

## Impact

- Archivos modificados: `frontend/src/screens/AdminDashboard.tsx`, `frontend/src/screens/ExamList.tsx`, `frontend/src/screens/Reports.tsx`, `frontend/src/screens/Revisor.tsx`, `frontend/src/screens/SessionDetail.tsx`, `frontend/src/screens/Proctor.tsx`, `frontend/src/screens/AuditPrivacy.tsx`
- Archivos nuevos (componentes extraídos): `frontend/src/screens/admin/components/` (colocalización igual que `alumno/components/` en C-41)
- Sin cambios en `api.ts`, `types.ts`, `store.ts` — solo UI/componentización
- Sin cambios en `AdminDetectionHarness.tsx` (herramienta de test, change propio)
- Dependencias: `C-40` (Button size, RangeInput, FormField, SectionTitle), `C-41` (patrón de colocalización en `screens/alumno/components/`)
