## Context

La plataforma ActiveExam acumuló dos problemas de presentación a lo largo de ~60 changes de implementación:

1. **Jerga interna visible**: códigos de regla de negocio (`RN-CO-01`) y de decisión de diseño (`D-4`) quedaron hardcodeados en texto visible al usuario final. No aportan valor al usuario; son artefactos del proceso de desarrollo que se filtraron a la UI.

2. **Repetición legal saturada**: "Ley 25.326" aparece en 15+ pantallas operativas. La repetición diluye la señal legal en los lugares donde sí importa (consentimiento, derechos del titular) y genera ruido visual en pantallas operativas. El spec `login-portal-reframe` exige que el footer del login la mencione — eso es el anchor mínimo necesario.

3. **Inputs del login sin componente reusable**: `FormularioJwt` usa `FormField + input nativo con clase .input`. El estilo `.input` tiene fondo gris de `surface-container-low`, tamaño compacto, sin íconos guía, y no comunica calidad. El próximo change c-61 (registro) necesita los mismos inputs — sin un `TextField` reusable, c-61 los reimplementaría de forma divergente.

**Constraints**:
- El spec `login-portal-reframe` exige que el footer del login mencione "Ley 25.326" → no se puede sacar del footer.
- El consentimiento informado (`EnrollmentConsentStep`, `AcuseExamen`, `Consent`) tiene contexto legal legítimo → se mantiene la mención donde introduce derechos.
- Paleta de color: los tokens de ActiveExam (primary violeta `#4241bc`, surface, on-surface-variant, outline) son los únicos colores permitidos. No se introduce ninguna paleta nueva.
- No buildear, no commitear sin pedido explícito.

## Goals / Non-Goals

**Goals:**
- Eliminar todos los códigos de jerga interna (`RN-XX`, `D-XX`) del texto visible al usuario.
- Reducir las menciones de "Ley 25.326" a los 4 anclajes legítimos definidos en la proposal.
- Crear el componente `TextField` en `frontend/src/ui/TextField.tsx` con la API acordada.
- Migrar `FormularioJwt` en `Login.tsx` a usar `TextField`.
- Dejar `TextField` listo para ser adoptado por c-61 sin modificaciones.

**Non-Goals:**
- Rediseñar la pantalla de login (layout, colores, aside, header — no se tocan).
- Cambiar los inputs de otras pantallas fuera del login en este change (c-61 lo hace).
- Modificar comentarios de código internos con "Ley 25.326" (solo aplica a texto visible al usuario en JSX).
- Agregar tests automatizados (fuera de scope de este change de pulido visual).
- Tocar lógica de autenticación ni stores.

## Decisions

### D-1: Crear `TextField.tsx` como archivo separado, no fusionarlo en `components.tsx`

`components.tsx` ya tiene 200+ líneas. Un componente con lógica propia (estado del toggle de password, íconos, ref forwarding) merece su propio archivo para legibilidad y para que c-61 pueda importarlo directamente.

**Alternativa descartada**: Ampliar `FormField` para aceptar íconos y `type`. Se descarta porque `FormField` es un wrapper genérico que renderiza `children` arbitrarios — no debe asumir que el hijo es un `<input>`. Mezclar responsabilidades rompe el principio de responsabilidad única.

### D-2: API del componente `TextField`

```tsx
interface TextFieldProps {
  label: string;
  name: string;
  type?: 'text' | 'email' | 'password' | 'search';
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  icon?: string;           // Material Symbol name — ícono izquierdo dentro del input
  error?: string;          // mensaje de error debajo del input
  hint?: string;           // texto de ayuda debajo del input (solo si no hay error)
  disabled?: boolean;
  required?: boolean;
  autoComplete?: string;
  className?: string;
}
```

- `type='password'` activa automáticamente el toggle ver/ocultar en el lado derecho.
- El ícono izquierdo (`icon`) ajusta el `padding-left` del input para no solaparse.
- `forwardRef` al `<input>` subyacente para accesibilidad y testabilidad.

**Alternativa descartada**: Pasar `showPasswordToggle` como prop separado. Se descarta porque el toggle de contraseña es comportamiento intrínseco de `type='password'` — no tiene sentido tenerlo en un campo de texto genérico.

### D-3: Estilos del `TextField` — fondo blanco + ring primario adaptado

```
bg-white
border border-outline-variant
rounded-xl
px-4 py-3       (cómodo en mobile)
shadow-xs
focus:ring-4 focus:ring-primary/15 focus:border-primary
hover:border-outline
transition-colors duration-150
```

- Con `icon`: `pl-10` para el padding izquierdo; el ícono se posiciona `absolute left-3`.
- Con toggle de password: `pr-10`; el botón de ojo se posiciona `absolute right-0`.
- Label: `text-sm font-medium text-on-surface-variant mb-1` (no uppercase, no tracking-wide — diferente de `FormField` para el contexto de login que es más cálido).

**Alternativa descartada**: Reusar la clase `.input` de `index.css` y solo sobreescribir. Se descarta porque `.input` tiene `bg-surface-container-low` hardcodeado y un tamaño compacto que contraría el objetivo. Una clase CSS global con overrides en Tailwind genera conflictos de especificidad.

### D-4: Migración del aside del Login — `Self-hosted · Ley 25.326 · DPIA aprobado` → `Self-hosted · DPIA aprobado`

El spec `login-portal-reframe` requiere que el **footer** mencione "Ley 25.326" — el footer se preserva intacto. El aside desktop es decorativo/branding, no el anchor legal requerido por el spec. Sacar la mención del aside reduce densidad sin violar el requisito.

Las 3 variantes (JWT, Demo, Keycloak) tienen el mismo aside → el cambio es idéntico en los 3 bloques.

### D-5: Criterio de conservación de "Ley 25.326" en pantallas operativas

| Contexto | Decisión | Razón |
|---|---|---|
| Footer global `shells.tsx:192` | CONSERVAR | Anchor global del sistema |
| `GlossaryPanel.tsx:74` | CONSERVAR | Glosario legal — contexto correcto |
| `EnrollmentConsentStep.tsx:114` | CONSERVAR | Texto del consentimiento informado — obligatorio legalmente |
| `AcuseExamen.tsx:215` | CONSERVAR | Art. 4 Ley 25.326 — finalidad del acuse |
| `Consent.tsx:67` | CONSERVAR | Introduce bloque de derechos del titular |
| `Login.tsx` footer (líneas 173/256/342) | CONSERVAR | Requerido por spec `login-portal-reframe` |
| `Login.tsx` aside (líneas 73/216/301) | SACAR | Decorativo; el footer ya cumple el requisito |
| `AuditPrivacy.tsx:34/64` | SACAR COLETILLA | Sacar `(Ley 25.326)` del texto visible; el título de la sección ya comunica el contexto |
| `StudentProfile.tsx:244/246` | SACAR | Pantalla operativa; el footer global cubre |
| `RequisitoBiometria.tsx:65` | SACAR COLETILLA | Sacar `(Ley 25.326)` — la frase sigue siendo clara |
| `RequisitoDni.tsx:45/62` | SACAR COLETILLA | Ídem |
| `ConfigureExam.tsx:160` | SACAR COLETILLA | El hint se reescribe sin la referencia |
| `Cierre.tsx:53` | SACAR | Reescribir en lenguaje claro sin la referencia legal |
| `ProctoringSessionDetail.tsx:93` | SACAR COLETILLA | La frase de revisión humana sigue siendo clara |
| `EnrollmentDniStep.tsx:128/150` | SACAR COLETILLA | Sacar del texto visible; comentarios internos se mantienen |
| `EnrollmentBiometricStep.tsx:266` | SACAR DEL TÍTULO | El título de la nota de privacidad no necesita la referencia |
| `ExamenResumenCard.tsx:39` | SACAR COLETILLA | El valor `"30 días"` es suficiente; la coletilla es ruido |

### D-6: `EnrollmentConsentStep.tsx:148` — sacar `RN-CO-01`

Texto actual: `"El acuse queda registrado con timestamp y hash inmutable (RN-CO-01). Podés solicitar acceso, rectificación y eliminación de tus datos ante la AAIP."`

Texto propuesto: `"El acuse queda registrado de forma permanente e inalterable. Podés solicitar acceso, rectificación y eliminación de tus datos ante la AAIP (Agencia de Acceso a la Información Pública)."`

Mantiene el mensaje legal; elimina el código interno; agrega la expansión de la sigla AAIP para usuarios no familiarizados.

### D-7: `CoverageChecklist.tsx:111` — sacar `D-4`

Texto actual: `"Aislamiento D-4: todos los eventos de esta sesión permanecen en el sink local. Ninguno se envía al backend de producción."`

Texto propuesto: `"Modo aislado: todos los eventos de esta sesión permanecen en el dispositivo local. Ninguno se envía al backend de producción."`

## Risks / Trade-offs

- **[Riesgo] Regresión visual en el login**: Migrar de `.input` a `TextField` cambia el layout del campo (padding, borde, fondo). → Mitigación: `TextField` usa las clases de Tailwind directamente sin clase CSS global; el revisor debe verificar visualmente en mobile y desktop antes de aprobar.

- **[Riesgo] Spec `login-portal-reframe` en conflicto**: El spec exige footer con "Ley 25.326" AND "Branding institucional intacto". Se conservan ambos en todas las variantes. → Mitigación: el delta spec de `login-portal-reframe` en este change documenta explícitamente que solo el aside cambia, no el footer.

- **[Riesgo] Accesibilidad del toggle de password**: El ícono izquierdo y el botón de ojo derecho reducen el área de texto. → Mitigación: `pl-10` (con ícono) y `pr-10` (con toggle) están calculados para no solaparse con texto de hasta ~30 chars en mobile sin corte.

- **[Trade-off] `TextField` no reemplaza `FormField` globalmente**: `FormField` sigue usándose en formularios complejos (ConfigureExam, enrollment). Coexistencia intencional — `TextField` es para inputs de login/registro tipo formulario de autenticación; `FormField` es para formularios de configuración con múltiples tipos de input.

## Migration Plan

No hay migraciones de base de datos ni de API. El cambio es puramente frontend:

1. Crear `frontend/src/ui/TextField.tsx`.
2. Exportar desde `frontend/src/ui/components.tsx`.
3. Migrar `FormularioJwt` en `Login.tsx`.
4. Aplicar cambios de copy en los archivos listados en la proposal (uno por uno, con verificación).
5. Rollback: cualquier cambio es trivialmente reversible con `git revert` — sin side effects de datos.

## Open Questions

- Ninguna. El scope está completamente definido por el inventario de la proposal.
