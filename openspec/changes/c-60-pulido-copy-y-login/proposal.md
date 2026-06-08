## Why

La plataforma muestra jerga interna de ingeniería directamente al usuario final (códigos como "RN-CO-01", "D-4") y repite la referencia "Ley 25.326" en 15+ pantallas operativas, diluyendo su relevancia legal y generando ruido visual. Adicionalmente, los inputs del formulario de login usan el estilo genérico `.input` (fondo gris, compacto) que no transmite la calidad visual que el producto merece, y no existe un componente `TextField` reusable que el próximo change de registro (c-61) pueda adoptar sin reinventar la rueda.

## What Changes

- **Frente 1 — Limpieza de copy**:
  - Eliminar el código `RN-CO-01` de `EnrollmentConsentStep.tsx:148` — reescribir en lenguaje claro sin romper el texto legal del consentimiento.
  - Eliminar el código `D-4` de `CoverageChecklist.tsx:111` — reescribir la nota de aislamiento en lenguaje llano.
  - Reducir las menciones de "Ley 25.326" en pantallas operativas: conservar SOLO en (a) footer global `shells.tsx:192`, (b) `GlossaryPanel.tsx:74`, (c) el texto del acuse de consentimiento (`EnrollmentConsentStep.tsx:114` y `AcuseExamen.tsx:215`) donde es contexto legal legítimo, y (d) `Consent.tsx:67` donde introduce el bloque de derechos. Sacar la coletilla `(Ley 25.326)` de pantallas operativas: `StudentProfile`, `RequisitoBiometria`, `RequisitoDni`, `ConfigureExam`, `Cierre`, `ProctoringSessionDetail`, `EnrollmentDniStep`, `EnrollmentBiometricStep`, `AuditPrivacy`, `ExamenResumenCard`.
  - En `Login.tsx`: las 3 variantes (JWT, Demo, Keycloak) tienen el footer "Tu privacidad está protegida — Ley 25.326". El spec `login-portal-reframe` exige que el footer mencione Ley 25.326; por tanto se conserva UNA sola mención discreta en el footer de cada variante (las líneas 173, 256, 342 ya son la única mención por variante — no hay duplicación). El aside desktop `Self-hosted · Ley 25.326 · DPIA aprobado` (líneas 73, 216, 301) se simplifica a `Self-hosted · DPIA aprobado` para reducir densidad legal sin romper el requisito del spec (el footer sigue mencionándola).

- **Frente 2 — Componente TextField reusable + inputs del login**:
  - Crear `frontend/src/ui/TextField.tsx`: componente reusable con label, ícono izquierdo, ícono derecho opcional (ojo de password), error, hint, fondo blanco, `rounded-xl`, padding cómodo, `shadow-xs`, focus ring del color primario adaptado a tokens de ActiveExam.
  - Exportar `TextField` desde `frontend/src/ui/components.tsx` (barrel export).
  - Migrar `FormularioJwt` en `Login.tsx` a usar `TextField` en lugar de `FormField + input nativo`.
  - c-61 (registro) depende de este componente — documentado en specs.

## Capabilities

### New Capabilities
- `login-input-textfield`: Componente `TextField` reusable — input con label, ícono, error, foco ring primario; API definida para ser adoptada por c-61 sin cambios.

### Modified Capabilities
- `login-portal-reframe`: El aside desktop pasa de `Self-hosted · Ley 25.326 · DPIA aprobado` a `Self-hosted · DPIA aprobado` en las 3 variantes. El footer sigue cumpliendo el requisito existente de mencionar Ley 25.326.

## Impact

- `frontend/src/ui/TextField.tsx` — archivo nuevo
- `frontend/src/ui/components.tsx` — barrel export de `TextField`
- `frontend/src/screens/Login.tsx` — aside simplificado, `FormularioJwt` migrado a `TextField`
- `frontend/src/screens/enrollment/EnrollmentConsentStep.tsx` — sacar `RN-CO-01` del texto visible
- `frontend/src/screens/harness/CoverageChecklist.tsx` — sacar `D-4`
- `frontend/src/screens/StudentProfile.tsx` — sacar `(Ley 25.326)` de líneas 244/246
- `frontend/src/screens/alumno/components/RequisitoBiometria.tsx` — sacar `(Ley 25.326)` de línea 65
- `frontend/src/screens/alumno/components/RequisitoDni.tsx` — sacar `(Ley 25.326)` de líneas 45/62
- `frontend/src/screens/ConfigureExam.tsx` — sacar `(Ley 25.326)` de línea 160
- `frontend/src/screens/Cierre.tsx` — sacar `Ley 25.326` de línea 53
- `frontend/src/screens/ProctoringSessionDetail.tsx` — sacar `(Ley 25.326)` de línea 93
- `frontend/src/screens/enrollment/EnrollmentDniStep.tsx` — sacar `(Ley 25.326)` de líneas 128/150
- `frontend/src/screens/enrollment/EnrollmentBiometricStep.tsx` — sacar `(Ley 25.326)` del título de nota (línea 266); conservar en comentario interno (línea 15/85)
- `frontend/src/screens/AuditPrivacy.tsx` — sacar `Ley 25.326` de líneas 34/64 de texto visible
- `frontend/src/screens/admin/components/ExamenResumenCard.tsx` — sacar `(Ley 25.326)` de línea 39
- Sin cambios de API backend. Sin migraciones de DB.
