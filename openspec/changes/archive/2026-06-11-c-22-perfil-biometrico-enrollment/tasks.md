## 1. student-profile-enrollment

- [x] 1.1 Crear la pantalla de Perfil del alumno (PascalCase: `StudentProfile.tsx`) con ruta dedicada — Done: la ruta renderiza el perfil y muestra el estado de enrollment.
- [x] 1.2 Modelar el estado de enrollment en Zustand (consentimiento, referencia, vigencia, vía alternativa) — Done: el store expone `enrollmentStatus` y `isProfileComplete` derivado.
- [x] 1.3 Orquestar el flujo de enrollment (consentimiento → referencia biométrica → DNI opcional) UNA sola vez — Done: tras completar, el perfil queda enrollado y no se re-pide en el pre-examen.
- [x] 1.4 Implementar el gate `perfil completo` = (consentimiento válido vigente o vía alternativa) + referencia vigente, y exponer `puedeRendir` (conecta con C-21) — Done: con perfil incompleto, inscribirse/rendir queda bloqueado; con perfil completo, habilitado.
- [x] 1.5 Mockear perfil/enrollment en `frontend/src/lib/api.ts` (get/save enrollment, estado de completitud) — Done: el mock devuelve el estado de perfil y persiste el enrollment de la demo.

## 2. informed-consent-presentation (MODIFIED) + consent-gate (MODIFIED)

- [x] 2.1 Reubicar la pantalla de consentimiento dentro del flujo de Perfil (fuera del pre-examen) — Done: el consentimiento se presenta en el perfil y ya no como paso de pre-examen.
- [x] 2.2 Mantener acción afirmativa sin casilla premarcada (RN-CO-02), texto versionado con acuse inmutable (RN-CO-01) y vía alternativa sin biometría (RN-CO-05) — Done: no hay casilla premarcada, el acuse referencia la versión exacta y existe la vía alternativa.
- [x] 2.3 Resolver el gate de consentimiento una sola vez en el perfil y reutilizarlo en todas las rendiciones — Done: el pre-examen no vuelve a pedir consentimiento si hay acuse válido en el perfil.
- [x] 2.4 Re-disparar el consentimiento cuando cambia la versión del texto — Done: un cambio de versión vuelve a exigir consentimiento antes de mantener el perfil completo.

## 3. embedding-computation (MODIFIED) + biometric-custody-encryption (MODIFIED/ADDED)

- [x] 3.1 Reutilizar el motor de visión existente (`frontend/src/vision/`, `liveness.ts`) para capturar el clip 3–5 s y calcular el embedding de referencia en el perfil — Done: la captura de referencia corre con MediaPipe + liveness y produce embedding.
- [x] 3.2 Persistir (mock) el embedding de referencia cifrado con metadatos de vigencia (captura, expiración, versión) — Done: el mock guarda embedding + vigencia, no en claro.
- [x] 3.3 Guardar la imagen de referencia del perfil como dato sensible (cifrada, finalidad acotada, eliminación al egreso, holds difieren, vigencia) — Done: el mock persiste la imagen de referencia con sus metadatos de custodia.
- [x] 3.4 Hacer que el pre-examen verifique 1:1 contra la referencia del perfil en vez de recapturar — Done: el pre-examen consume la referencia enrollada y no recalcula una nueva.

## 4. biometric-reference-renewal

- [x] 4.1 Definir el período de vigencia configurable (default 24 meses, no hardcode) y calcular `expires_at` al capturar — Done: la referencia recibe expiración derivada de la config.
- [x] 4.2 Tratar la referencia caducada como no vigente: bloquear rendir, permitir gestionar perfil y solicitar renovación — Done: con referencia caducada el alumno no puede rendir hasta renovar.
- [x] 4.3 Modelar la renovación anticipada gatillada por deriva del embedding (verificación silenciosa continua), sin sancionar la rendición en curso — Done: la deriva sostenida marca renovación pero no invalida ni sanciona la rendición.
- [x] 4.4 UI de renovación en el perfil (estado vigente / por vencer / caducada / renovación requerida) — Done: el perfil muestra el estado de vigencia y permite renovar.

## 5. optional-dni-scan

- [x] 5.1 Agregar el paso de DNI detrás de un feature flag, opcional y no bloqueante — Done: con flag off el paso es opcional/próximamente y no bloquea el perfil completo.
- [x] 5.2 Tratar el DNI capturado como dato sensible bajo custodia (cifrado, finalidad acotada, eliminación al egreso, holds difieren) — Done: el mock persiste el DNI con los mismos resguardos que la imagen de referencia.
- [x] 5.3 Documentar el resguardo legal del DNI en la UI/copy (Ley 25.326) — Done: la pantalla informa el tratamiento del DNI como dato sensible.

## 6. Validación

- [x] 6.1 `openspec validate c-22-perfil-biometrico-enrollment --strict` pasa sin errores — Done: la validación estricta es verde.
