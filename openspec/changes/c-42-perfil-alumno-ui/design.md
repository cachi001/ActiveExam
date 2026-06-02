## Context

`StudentProfile.tsx` es la pantalla más grande del frontend (~700 líneas). Implementa una máquina de estados con el tipo `PasoEnrollment` (`cargando | perfil | consentimiento | foto_perfil | biometria | dni | renovar_biometria`). Los pasos de enrollment (`consentimiento`, `foto_perfil`, `biometria`, `dni`, `renovar_biometria`) ya delegan a componentes propios (`EnrollmentConsentStep`, `CameraSnapshotCapture`, `EnrollmentBiometricStep`, `EnrollmentDniStep`, `BiometricRenewalStatus`). El problema está en `paso === 'perfil'`: toda la vista principal está inline — el encabezado con avatar, tres banners condicionales, y cuatro secciones de requisitos (cada una un `<Card>` con badge, descripción, botón CTA) totalizando ~350 líneas de JSX sin extraer.

Las primitivas del design system ya disponibles son: `Card`, `Badge`, `Button`, `Icon`, `SectionTitle`, `Stat`, `Avatar` (`ui/components.tsx`), `Term` (`ui/Term.tsx`). La carpeta `frontend/src/screens/alumno/components/` ya existe con 6 componentes de C-41 como patrón de referencia.

## Goals / Non-Goals

**Goals:**
- Extraer la vista `paso==='perfil'` en tres componentes de presentación pura
- Lograr que `StudentProfile` en esa vista sea un orquestador delgado (handlers + `enrollment` state → props hacia abajo)
- Unificar las cuatro secciones de requisitos bajo un patrón único `RequisitoCard` — un solo componente parametrizable es más DRY que cuatro componentes específicos (`ConsentimientoCard`, `BiometriaCard`, etc.)
- Look minimalista: tarjetas uniformes, badges consistentes, tamaños de botón adecuados, espaciado correcto — que se entienda de un vistazo qué falta
- Mantener el contexto legal y L2.5 (notas Ley 25.326, Term tooltips, disclaimer "decisión siempre humana") — no se eliminan, se encapsulan en los componentes

**Non-Goals:**
- Cambiar la lógica de fases, el gate `perfil_completo`, los handlers o la navegación
- Modificar los pasos de enrollment (`EnrollmentConsentStep`, `EnrollmentBiometricStep`, `EnrollmentDniStep`, `CameraSnapshotCapture`, `BiometricRenewalStatus`)
- Introducir nuevas funcionalidades al perfil
- Mover el bloque `DEV_TOOLS_ENABLED` (simulación de deriva) — permanece en `StudentProfile`
- Modificar el backend o la API mock

## Decisions

### D-1: Un `RequisitoCard` genérico parametrizable vs cuatro componentes específicos

**Decisión**: Un solo `RequisitoCard` genérico.

**Razonamiento**: Los cuatro requisitos (consentimiento, biometría, foto, DNI) tienen la misma estructura visual: ícono + título + badge de estado + detalle (slot con `children`) + acción (botón CTA opcional). Un componente único con props tipadas elimina la duplicación de los cuatro `<Card className="space-y-md">` actuales. Los cuatro wrappers específicos opcionales (`ConsentimientoCard`, `BiometriaCard`, etc.) no agregan valor — la lógica de qué mostrar vive en `StudentProfile` de todas formas.

**Alternativa descartada**: Cuatro componentes específicos. Requiere mantener cuatro archivos para el mismo patrón visual; no tiene ventaja de reutilización.

**Props de `RequisitoCard`**:

```tsx
interface RequisitoCardProps {
  icon: string;                                          // Material Symbols name
  title: string;
  badge: { tone: BadgeTone; label: string };
  action?: ReactNode;                                    // Botón CTA, opcional
  children?: ReactNode;                                  // Detalle/contenido interno
  className?: string;
}
```

El encabezado (ícono + título + badge) es fijo. El contenido interno (`children`) y el CTA (`action`) son slots: cada uso en `StudentProfile` pasa su propio contenido según el estado del requisito.

### D-2: `PerfilHeaderCard` — avatar condicional centralizado

**Decisión**: Componente que recibe `principal` y renderiza: avatar circular (`foto_perfil` → `<img>`, sin foto → inicial en `secondary-container`) + nombre, roles, y grid 2×2 de datos personales (legajo, email, institución, jurisdicción).

**Razonamiento**: El patrón de avatar condicional (foto circular vs inicial) ya fue establecido en C-37 y aparece también en la sidebar del shell. Centralizarlo en `PerfilHeaderCard` evita que el patrón se duplique en futuros cambios al perfil.

**Props**:
```tsx
interface PerfilHeaderCardProps {
  principal: Principal | null;
}
```

Recibe `principal` completo del store; el componente no accede al store directamente (presentación pura).

### D-3: `PerfilBannerEstado` — tres banners en un solo componente

**Decisión**: Un componente que recibe un objeto de estado del perfil y renderiza condicionalmente el banner correcto (o nada si el perfil está ok y sin alertas).

**Razonamiento**: Los tres banners (`perfilCompleto`, `biometriaCaducada`, `biometriaRenovacionRequerida`) comparten la estructura `flex + Icon + texto + Button`. Encapsularlos elimina 60+ líneas de condicionales inline y los unifica en un solo componente fácil de mantener.

**Props**:
```tsx
interface PerfilBannerEstadoProps {
  perfilCompleto: boolean;
  biometriaCaducada: boolean;
  biometriaRenovacionRequerida: boolean;
  viaAlternativa: boolean;
  onIrAExamenes: () => void;
  onRenovarBiometria: () => void;
}
```

El banner de caducada tiene prioridad sobre renovacionRequerida. Si `perfilCompleto && !caducada && !renovacion` → banner verde. Si `caducada` → banner rojo. Si `renovacion && !caducada` → banner amarillo. Si `!perfilCompleto && !caducada && !renovacion` → no renderiza nada (el CTA de enrollment está en cada `RequisitoCard`).

### D-4: Ubicación de los componentes

**Decisión**: `frontend/src/screens/alumno/components/` — misma carpeta que los componentes de C-41.

**Razonamiento**: La carpeta ya existe y contiene componentes del alumno (`QuickAccessCard`, `ExamenProximoCard`, etc.). El perfil es parte del portal del alumno — la colocalización es coherente.

### D-5: Orden visual del perfil

La vista `paso==='perfil'` queda con esta estructura:

```
<StudentShell>
  <div className="max-w-2xl mx-auto space-y-xl">
    <header>           ← h1 "Mi perfil" + subtítulo (queda en StudentProfile)
    <PerfilHeaderCard> ← avatar + datos personales
    <PerfilBannerEstado> ← banner contextual (completo / caducada / renovacion)

    <RequisitoCard icon="gavel" title="Consentimiento informado" ...>
      {/* consentimientoOk: acuse con versión/fecha/hash; !ok: CTA "Leer y consentir" */}
    </RequisitoCard>

    {!viaAlternativa && (
      <RequisitoCard icon="face" title="Referencia biométrica" ...>
        {/* biometriaOk: <BiometricRenewalStatus>; !ok: nota + CTA "Capturar" */}
        {DEV_TOOLS_ENABLED && biometriaOk && ... dev tools block}
      </RequisitoCard>
    )}

    <RequisitoCard icon="badge" title="Verificación documental" ...>
      {/* dniOk + analisis: badges; dniOk sin analisis: fechas; !ok + ENABLE_DNI_SCAN: CTA; !ok sin flag: nota */}
    </RequisitoCard>

    {perfilCompleto && <div className="text-center"><Button ...>Ir a mis exámenes</Button></div>}
  </div>
</StudentShell>
```

Nota: el paso `foto_perfil` no tiene sección propia en la vista del perfil — solo existe como paso del flujo. La foto se muestra en `PerfilHeaderCard` (avatar circular cuando existe).

## Risks / Trade-offs

- [Riesgo: foto sin sección dedicada] La foto de perfil no tiene una `RequisitoCard` propia en la vista del perfil. La foto se ve en el avatar de `PerfilHeaderCard` cuando existe. Si se requiere en el futuro mostrar el estado de la foto como requisito explícito, hay que agregar una cuarta card. → Por ahora el requisito es implícito (el avatar lo refleja). El task correspondiente documenta esta decisión.

- [Riesgo: `BiometricRenewalStatus` anidado en `RequisitoCard`] El componente de vigencia ya tiene su propia estructura interna (`space-y-md`, grid de fechas, botón). Anidarlo en el slot `children` de `RequisitoCard` puede generar doble padding. → `RequisitoCard` usa `p-lg` en el header; el `children` slot no agrega padding extra — el componente anidado gestiona su propio espaciado.

- [Trade-off: granularidad de los wrappers] Se decidió NO crear `ConsentimientoCard`, `BiometriaCard`, etc. como archivos separados. El contenido interno de cada requisito vive como JSX inline en `StudentProfile` pasado como `children`. Esto significa que `StudentProfile` todavía tiene ~150 líneas de JSX después del refactor (vs ~350 antes). Es una reducción significativa pero no una extracción total. → La extracción total requeriría que cada card reciba todos los props de estado como props propias — aumenta el acoplamiento sin ganancia de legibilidad.

## Open Questions

- **¿Agregar `FotoCard` explícita?** Hoy la foto solo aparece en el avatar. Si product decide que la foto debe ser un requisito explícito con estado (`capturada` / `pendiente`) visible en la lista del perfil, hay que agregar una `RequisitoCard` para ella. Decisión: fuera del scope de C-42; documentada como extensión futura.
- **¿`PerfilHeaderCard` en la sidebar también?** El avatar condicional se repite en la sidebar de `StudentShell`. La unificación total requeriría pasar `principal` a la sidebar. Fuera del scope; no bloquea C-42.
