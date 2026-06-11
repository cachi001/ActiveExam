## 1. Componente TextField reusable

- [x] 1.1 Crear `frontend/src/ui/TextField.tsx` con la interfaz `TextFieldProps` definida en design.md (props: `label`, `name`, `type`, `value`, `onChange`, `placeholder`, `icon`, `error`, `hint`, `disabled`, `required`, `autoComplete`, `className`); implementar `forwardRef` al `<input>` subyacente
- [x] 1.2 Implementar estilos del input: `bg-white border border-outline-variant rounded-xl px-4 py-3 shadow-xs focus:ring-4 focus:ring-primary/15 focus:border-primary hover:border-outline transition-colors duration-150 w-full disabled:opacity-50`
- [x] 1.3 Implementar label con `text-sm font-medium text-on-surface-variant mb-1`; mensaje de error con `text-label-sm text-error` y borde de error cuando `error` está presente; hint con `text-label-sm text-on-surface-variant` (solo si no hay error)
- [x] 1.4 Implementar ícono izquierdo: cuando `icon` está presente, renderizar `<Icon name={icon} />` con `absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-[20px]` y aplicar `pl-10` al input
- [x] 1.5 Implementar toggle ver/ocultar contraseña: cuando `type='password'`, gestionar estado `showPassword` interno y renderizar botón con ícono `visibility`/`visibility_off` a la derecha (`absolute right-0 inset-y-0`); aplicar `pr-10` al input
- [x] 1.6 Exportar `TextField` en `frontend/src/ui/components.tsx` (agregar al barrel: `export { TextField } from './TextField'`)

## 2. Migrar FormularioJwt al TextField

- [x] 2.1 En `frontend/src/screens/Login.tsx`, reemplazar el bloque `<FormField label="Usuario o email"><input ...></FormField>` por `<TextField label="Usuario o email" name="username" icon="person" ... />` usando los tokens correspondientes
- [x] 2.2 Reemplazar el bloque `<FormField label="Contraseña"><div className="relative"><input ...><button (ojo)></div></FormField>` por `<TextField label="Contraseña" name="password" type="password" icon="lock" ... />`; el toggle de ojo queda encapsulado en `TextField`, eliminar el estado `verPassword` local y el JSX del botón de ojo de `FormularioJwt`
- [x] 2.3 Verificar que el error de credenciales inválidas sigue renderizándose correctamente (bloque `{error && ...}` — no lo mueve `TextField`, sigue siendo externo)

## 3. Limpieza de copy — jerga interna

- [x] 3.1 `frontend/src/screens/enrollment/EnrollmentConsentStep.tsx:148` — reemplazar `"El acuse queda registrado con timestamp y hash inmutable (RN-CO-01). Podés solicitar acceso, rectificación y eliminación de tus datos ante la AAIP."` por `"El acuse queda registrado de forma permanente e inalterable. Podés solicitar acceso, rectificación y eliminación de tus datos ante la AAIP (Agencia de Acceso a la Información Pública)."`
- [x] 3.2 `frontend/src/screens/harness/CoverageChecklist.tsx:111` — reemplazar `"Aislamiento D-4: todos los eventos de esta sesión permanecen en el sink local. Ninguno se envía al backend de producción."` por `"Modo aislado: todos los eventos de esta sesión permanecen en el dispositivo local. Ninguno se envía al backend de producción."`

## 4. Reducir redundancia "Ley 25.326" — Login (aside desktop)

- [x] 4.1 `frontend/src/screens/Login.tsx:73` (aside `FormularioJwt`) — cambiar `Self-hosted · Ley 25.326 · DPIA aprobado` a `Self-hosted · DPIA aprobado`
- [x] 4.2 `frontend/src/screens/Login.tsx:216` (aside `SelectorRolDemo`) — ídem
- [x] 4.3 `frontend/src/screens/Login.tsx:301` (aside `LoginKeycloak`) — ídem
- [x] 4.4 Verificar que el footer de cada variante (líneas 173, 256, 342) permanece intacto con "Tu privacidad está protegida — Ley 25.326"

## 5. Reducir redundancia "Ley 25.326" — pantallas operativas

- [x] 5.1 `frontend/src/screens/StudentProfile.tsx:244` — reescribir la nota de privacidad eliminando `(Ley 25.326)` manteniendo la sustancia: "La foto de perfil se procesa server-side y se elimina al egreso."
- [x] 5.2 `frontend/src/screens/alumno/components/RequisitoBiometria.tsx:65` — cambiar `Privacidad (Ley 25.326): La imagen y el <Term termKey="embedding" />` por `Privacidad: La imagen y el <Term termKey="embedding" />`
- [x] 5.3 `frontend/src/screens/alumno/components/RequisitoDni.tsx:45` — sacar `(Ley 25.326)` de "Tratado como dato sensible (Ley 25.326): cifrado at-rest..."
- [x] 5.4 `frontend/src/screens/alumno/components/RequisitoDni.tsx:62` — sacar `(Ley 25.326)` de "será tratado como dato sensible (Ley 25.326): cifrado..."
- [x] 5.5 `frontend/src/screens/ConfigureExam.tsx:160` — cambiar el hint `"Por defecto 30 días (Ley 25.326). Luego se elimina automáticamente."` por `"Por defecto 30 días. Los datos se eliminan automáticamente al vencer el plazo."`
- [x] 5.6 `frontend/src/screens/Cierre.tsx:53` — reescribir `"Conforme al reglamento y la Ley 25.326, tus datos biométricos se eliminan automáticamente a los 30 días, salvo apelación o hold disciplinario abierto."` por `"Tus datos biométricos se eliminan automáticamente a los 30 días del egreso, salvo que haya una apelación o proceso disciplinario abierto."`
- [x] 5.7 `frontend/src/screens/ProctoringSessionDetail.tsx:93` — sacar `(Ley 25.326)` de la mención "dato sensible (Ley 25.326)" en el párrafo de revisión humana
- [x] 5.8 `frontend/src/screens/enrollment/EnrollmentDniStep.tsx:128` — sacar `(Ley 25.326)` del texto visible al usuario
- [x] 5.9 `frontend/src/screens/enrollment/EnrollmentDniStep.tsx:150` — sacar `(Ley 25.326)` del texto visible al usuario
- [x] 5.10 `frontend/src/screens/enrollment/EnrollmentBiometricStep.tsx:266` — cambiar el título de la nota `"Privacidad y custodia de datos (Ley 25.326)"` por `"Privacidad y custodia de datos"`
- [x] 5.11 `frontend/src/screens/AuditPrivacy.tsx:34` — sacar `Ley 25.326` de "Registro inmutable de acciones, cadena de custodia y derechos del titular bajo Ley 25.326." → `"Registro inmutable de acciones y cadena de custodia. Derechos del titular disponibles abajo."`
- [x] 5.12 `frontend/src/screens/AuditPrivacy.tsx:64` — el `sub` del SectionTitle `"Ley 25.326 · AAIP"` → cambiar a solo `"AAIP"` (la mención de la ley ya aparece en el contexto del glosario y footer)
- [x] 5.13 `frontend/src/screens/admin/components/ExamenResumenCard.tsx:39` — cambiar `value={`${examen.retencion_dias} días (Ley 25.326)`}` por `value={`${examen.retencion_dias} días`}`

## 6. Verificación de invariantes

- [x] 6.1 Verificar que `EnrollmentConsentStep.tsx:114` conserva `<strong>Ley 25.326</strong>` en el texto del consentimiento informado (no debe haberse tocado)
- [x] 6.2 Verificar que `AcuseExamen.tsx:215` conserva `"conforme al art. 4 de la Ley 25.326"` en el texto del acuse
- [x] 6.3 Verificar que `Consent.tsx:67` conserva `<strong>Ley 25.326</strong>` en el bloque de derechos
- [x] 6.4 Verificar que `shells.tsx:192` y `GlossaryPanel.tsx:74` no fueron tocados
- [x] 6.5 Buscar con `rg "RN-[A-Z]+-[0-9]+" frontend/src --include="*.tsx"` para confirmar que no quedan más códigos de regla de negocio en texto visible (fuera de comentarios de código)
- [x] 6.6 Buscar con `rg '"D-[0-9]' frontend/src --include="*.tsx"` para confirmar que no quedan más códigos `D-X` en strings JSX visibles
