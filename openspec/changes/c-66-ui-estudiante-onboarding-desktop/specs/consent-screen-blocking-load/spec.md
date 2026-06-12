## ADDED Requirements

### Requirement: Consent.tsx NO renderiza checkbox ni botón hasta tener texto del consentimiento

La pantalla `Consent.tsx` SHALL bloquear el render del checkbox de aceptación, del botón "Acepto y continúo" y de las cláusulas del consentimiento hasta que el state `texto` (resultado de `api.getConsentText()`) sea distinto de `null`. Mientras `texto === null`, la pantalla SHALL mostrar el `LoadingSpinner` (morado centrado) con label `Cargando consentimiento…` y nada más.

#### Scenario: Texto del consentimiento todavía no llegó
- **WHEN** el estudiante entra a `/consent` y `api.getConsentText()` aún no resolvió
- **THEN** la pantalla muestra solo el `LoadingSpinner` con label `Cargando consentimiento…`. NO se renderiza el checkbox ni el botón "Acepto y continúo" ni las cláusulas

#### Scenario: Texto del consentimiento llegó
- **WHEN** `api.getConsentText()` resuelve y `texto` deja de ser `null`
- **THEN** la pantalla muestra TODO de una vez: el bloque de cláusulas (grilla de bloques), el checkbox de aceptación, el botón "Acepto y continúo" y el link de "solicitar vía alternativa"

#### Scenario: Botón "Acepto" NUNCA aparece antes que las cláusulas
- **WHEN** el estudiante observa la pantalla `/consent` desde el primer render hasta que termina la carga
- **THEN** en ningún momento el botón "Acepto y continúo" es visible si la grilla de cláusulas no es visible aún

### Requirement: El bloqueo de carga aplica también a la rama liviana

Cuando el estudiante ya consintió en su perfil con versión vigente (`yaConsintioPerfil === true`), el render del check "Confirmo que acepto…" + botón "Confirmar y continuar" SHALL esperar a que `texto` esté disponible para comparar la versión del acuse contra `texto.version`.

#### Scenario: Rama liviana también bloquea hasta tener texto
- **WHEN** el estudiante ya tiene `acusePerfil` válido pero `texto` aún no llegó
- **THEN** la pantalla muestra el `LoadingSpinner` hasta que `texto` esté disponible — solo entonces decide si renderiza rama liviana o completa
