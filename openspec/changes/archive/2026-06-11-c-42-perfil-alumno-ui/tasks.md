## 1. RequisitoCard — componente base

- [x] 1.1 Crear `frontend/src/screens/alumno/components/RequisitoCard.tsx` — interfaz `RequisitoCardProps` con `icon: string`, `title: string`, `badge: { tone: 'neutral' | 'primary' | 'success' | 'warning' | 'error'; label: string }`, `action?: ReactNode`, `children?: ReactNode`, `className?: string`
- [x] 1.2 Implementar el encabezado de `RequisitoCard`: `flex items-center justify-between` con `Icon` + `h2` (título) a la izquierda y `Badge` con `tone` y `dot` a la derecha
- [x] 1.3 Implementar el cuerpo de `RequisitoCard`: debajo del encabezado, renderizar `children` cuando existan; renderizar `action` debajo del cuerpo cuando exista
- [x] 1.4 Usar `Card` de `ui/components.tsx` como contenedor raíz con `className="space-y-md"`; verificar que no se genera doble padding cuando `children` es `BiometricRenewalStatus`
- [x] 1.5 Exportar `RequisitoCard` como export nombrado

## 2. PerfilHeaderCard — encabezado con avatar y datos personales

- [x] 2.1 Crear `frontend/src/screens/alumno/components/PerfilHeaderCard.tsx` — interfaz `PerfilHeaderCardProps` con `principal: Principal | null` (importar `Principal` de `../../lib/types`)
- [x] 2.2 Implementar avatar condicional: si `principal?.foto_perfil` → `<img src={principal.foto_perfil} className="w-14 h-14 rounded-full object-cover shrink-0" />`; si no → div circular `w-14 h-14 rounded-full bg-secondary-container` con `principal?.nombre.charAt(0) ?? '?'` en `font-headline text-headline-sm`
- [x] 2.3 Implementar bloque de nombre y roles: `text-label-lg font-semibold text-on-surface` para el nombre y `text-label-sm text-on-surface-variant` para los roles (`principal?.roles.join(', ')`)
- [x] 2.4 Implementar grid 2×2 de datos personales con patrón `text-label-sm text-on-surface-variant uppercase tracking-wide` para la etiqueta y `text-label-md text-on-surface font-semibold` para el valor — campos: Legajo (`id_institucional`), Email institucional, Institución ('UTN Regional Mendoza' hardcoded), Jurisdicción
- [x] 2.5 Usar `Card` como contenedor; flex row para avatar + datos; grid de datos debajo con `grid-cols-1 sm:grid-cols-2 gap-md`
- [x] 2.6 Exportar `PerfilHeaderCard` como export nombrado

## 3. PerfilBannerEstado — banners contextuales

- [x] 3.1 Crear `frontend/src/screens/alumno/components/PerfilBannerEstado.tsx` — interfaz `PerfilBannerEstadoProps` con: `perfilCompleto: boolean`, `biometriaCaducada: boolean`, `biometriaRenovacionRequerida: boolean`, `viaAlternativa: boolean`, `onIrAExamenes: () => void`, `onRenovarBiometria: () => void`
- [x] 3.2 Implementar banner verde (`perfilCompleto && !biometriaCaducada && !biometriaRenovacionRequerida`): `bg-success-container border border-success/30 rounded-xl p-md`, ícono `verified` fill, texto "Perfil completo — podés rendir tus exámenes", subtexto condicional por `viaAlternativa`, `Button variant='secondary'` "Mis exámenes" que llama `onIrAExamenes`
- [x] 3.3 Implementar banner rojo (`biometriaCaducada`): `bg-error-container border border-error/30`, ícono `cancel` fill, texto "Referencia biométrica caducada — no podés rendir", `Button variant='danger' size='sm'` "Renovar" que llama `onRenovarBiometria`
- [x] 3.4 Implementar banner amarillo (`biometriaRenovacionRequerida && !biometriaCaducada`): `bg-warning-container border border-warning/30`, ícono `refresh`, texto "Renovación biométrica requerida", referencias a `<Term termKey="embedding" />` y `<Term termKey="l2_5" />`, `Button variant='outline' size='sm'` "Renovar" que llama `onRenovarBiometria`
- [x] 3.5 Retornar `null` cuando ninguna condición aplica (sin banner)
- [x] 3.6 Importar `Term` de `../../ui/Term`; exportar `PerfilBannerEstado` como export nombrado

## 4. Refactor de StudentProfile — vista paso==='perfil'

- [x] 4.1 Agregar imports en `StudentProfile.tsx`: `PerfilHeaderCard`, `RequisitoCard`, `PerfilBannerEstado` desde `./alumno/components/`
- [x] 4.2 Reemplazar el bloque `<Card>` de datos personales con `<PerfilHeaderCard principal={principal} />`
- [x] 4.3 Reemplazar los tres banners condicionales (éxito/error/warning) con `<PerfilBannerEstado perfilCompleto={perfilCompleto} biometriaCaducada={biometriaCaducada} biometriaRenovacionRequerida={biometriaRenovacionRequerida} viaAlternativa={viaAlternativa} onIrAExamenes={() => navigate('/alumno/mis-examenes')} onRenovarBiometria={handleRenovarBiometria} />`
- [x] 4.4 Reemplazar el bloque `<Card>` de consentimiento con `<RequisitoCard icon="gavel" title="Consentimiento informado" badge={...}>` — el `children` preserva el contenido interno existente (acuse con versión/fecha/hash, nota de vía alternativa, o el bloque de "pendiente" con botón "Leer y consentir")
- [x] 4.5 Reemplazar el bloque `{!viaAlternativa && <Card>}` de biometría con `{!viaAlternativa && <RequisitoCard icon="face" title="Referencia biométrica" badge={...}>}` — el `children` incluye `BiometricRenewalStatus` o el bloque pendiente (nota de privacidad + botón); preservar el bloque `DEV_TOOLS_ENABLED` dentro del `children` de la card
- [x] 4.6 Reemplazar el bloque `<Card>` de DNI con `<RequisitoCard icon="badge" title="Verificación documental" badge={...}>` — el `children` preserva la lógica con IIFE de `AnalisisDNI`, el fallback sin análisis, y el CTA de escáner DNI opcional
- [x] 4.7 Verificar que el badge de la `RequisitoCard` de biometría refleja correctamente todos los estados: 'Pendiente' (warning), 'Vigente' (success), 'Caducada' (error), 'Por vencer' (warning), 'Renovación requerida' (warning) — misma lógica de tone que el `Badge` inline actual
- [x] 4.8 Verificar que el CTA de la `RequisitoCard` del perfil completo (`<Button onClick={() => navigate('/alumno/mis-examenes')}>Ir a mis exámenes</Button>`) queda debajo de todas las cards; no lo mover dentro de ningún componente
- [x] 4.9 Asegurarse de que la firma de imports no tiene duplicados y que no quedan blocks muertos en la vista `paso === 'perfil'`

## 5. Actualización de CHANGES.md

- [x] 5.1 Agregar entrada `C-41` (completada en la sesión anterior — `c-41-login-portal-alumno-ui`, validate OK, 63 tasks) en la sección de refinamiento post-fundación de CHANGES.md, con estado `[x] aplicado`
- [x] 5.2 Agregar entrada `C-42` (`c-42-perfil-alumno-ui`) en la sección de refinamiento post-fundación de CHANGES.md con estado `[ ] propuesto (validate --strict OK)`, scope resumido, dependencias, governance, y "Leer antes"
- [x] 5.3 Actualizar el resumen de totales al final de CHANGES.md (de 40 a 42 changes; actualizar la lista de "Refinamiento post-fundación" y el párrafo de descripción)

## 6. Validación

- [x] 6.1 Ejecutar `openspec validate --strict` y verificar que no hay errores en el change `c-42-perfil-alumno-ui`
- [x] 6.2 Verificar que `PerfilHeaderCard` en `paso === 'perfil'` muestra el avatar circular cuando `principal.foto_perfil` existe, e inicial cuando no
- [x] 6.3 Verificar que `PerfilBannerEstado` muestra el banner correcto para cada combinación de estado: `perfilCompleto && !caducada && !renovacion` → verde; `caducada` → rojo; `renovacion && !caducada` → amarillo; ninguna condición → sin banner
- [x] 6.4 Verificar que cada `RequisitoCard` tiene el badge correcto según el estado de `enrollment`: consentimiento (completado/pendiente/vía alternativa), biometría (vigente/caducada/por vencer/renovación requerida/pendiente), DNI (registrado/pendiente/no disponible)
- [x] 6.5 Verificar que el bloque `DEV_TOOLS_ENABLED` (simulación de deriva del embedding) sigue visible en la `RequisitoCard` de biometría cuando `DEV_TOOLS_ENABLED && biometriaOk && !biometriaCaducada && !biometriaRenovacionRequerida`
- [x] 6.6 Verificar que la máquina de fases (`setPaso`) no fue afectada: todos los pasos (`consentimiento`, `foto_perfil`, `biometria`, `dni`, `renovar_biometria`) siguen funcionando al navegar desde la vista del perfil
- [x] 6.7 Verificar que `tsc --noEmit` no reporta errores de TypeScript en ninguno de los archivos nuevos o modificados
