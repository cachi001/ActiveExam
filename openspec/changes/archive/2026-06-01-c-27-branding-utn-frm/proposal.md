## Why

El frontend actual contiene 13 referencias hardcodeadas a "UBA" / "Universidad de Buenos Aires" dispersas en shells, pantalla de login, panel de revisor y datos mock — todas incorrectas: la institución real es **UTN Regional Mendoza (FRM)**. Además los mocks incluyen materias de Medicina que no corresponden a ninguna carrera UTN. Centralizar la identidad institucional en un único módulo de configuración elimina la inconsistencia, previene regresiones futuras y sienta la base para soporte multi-tenant (VITE_INSTITUTION_*).

## What Changes

- **Nuevo módulo de configuración institucional** `frontend/src/config/institution.ts` con el objeto canónico de identidad UTN FRM (nombre completo, nombre corto, sigla, dominio de email, ID prefix) y soporte de override por variables de entorno VITE_INSTITUTION_*.
- **Corrección de `frontend/src/ui/shells.tsx`**: footer "Self-hosted · UBA" → "Self-hosted · UTN FRM" y "Soporte UBA" → "Soporte UTN FRM" (leer de config central).
- **Corrección de `frontend/src/screens/Login.tsx`**: título "Universidad de Buenos Aires — UBA" → "Universidad Tecnológica Nacional — Facultad Regional Mendoza" y botón "Ingresar con UBA ID" → "Ingresar con UTN FRM ID" (leer de config central).
- **Corrección de `frontend/src/screens/Revisor.tsx`**: "UBA Medicina · ..." → "UTN FRM · ..." (leer de config central).
- **Corrección de `frontend/src/screens/ConfigureExam.tsx`**: id de examen mock `EX-UBA-...` → `EX-FRM-...` (usar prefix de config central).
- **Corrección de `frontend/src/lib/api.ts` — staff mock**: `id_institucional: 'UBA-DOC-1182'` → `'FRM-DOC-1182'`, emails `@uba.ar` → `@frm.utn.edu.ar` (usar dominio de config central).
- **Corrección de `frontend/src/lib/api.ts` — exámenes mock**: IDs `EX-UBA-ANAT-I`, `EX-UBA-FISIO-II`, `EX-UBA-QUIM-ORG`, `EX-UBA-HISTO` → IDs UTN FRM con materias coherentes con carreras de ingeniería (Análisis Matemático I, Física I, Algoritmos y Estructuras de Datos, Sistemas de Representación).
- Los nombres de materias de Medicina (Anatomía, Fisiología, Química Orgánica, Histología) son reemplazados por materias canónicas de Ingeniería UTN.

**No hay cambios de comportamiento, rutas de API, lógica de negocio ni contratos de autenticación.**

## Capabilities

### New Capabilities

- `institution-config`: Módulo de configuración centralizada de identidad institucional para el frontend. Expone un objeto TypeScript tipado con los datos de UTN FRM y soporte de override por VITE_INSTITUTION_* para futura multi-tenancy. Todos los puntos de UI que muestran branding institucional leen de este módulo.

### Modified Capabilities

<!-- No hay specs de capabilities pre-existentes en este proyecto aún (openspec/specs/ vacío). -->

## Impact

- **Archivos modificados**:
  - `frontend/src/config/institution.ts` — nuevo (creado)
  - `frontend/src/ui/shells.tsx` — 2 referencias UBA
  - `frontend/src/screens/Login.tsx` — 2 referencias UBA
  - `frontend/src/screens/Revisor.tsx` — 1 referencia UBA
  - `frontend/src/screens/ConfigureExam.tsx` — 1 referencia UBA en mock ID
  - `frontend/src/lib/api.ts` — ~8 referencias UBA en datos mock (staff + exámenes)
- **Dependencias**: ninguna nueva (solo cambios de strings y creación de un módulo de config puro TypeScript)
- **APIs / contratos**: sin cambio (solo UI strings y datos mock del frontend)
- **Tests**: ningún test existente afectado (cambios cosméticos y de datos mock)
- **LEGACY IGNORADO**: `frontend/src/screens/html/StyleGuide.html` — archivo muerto, no se usa, no se toca
