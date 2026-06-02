## ADDED Requirements

### Requirement: PerfilBannerEstado encapsula los banners contextuales del estado del perfil
El sistema SHALL proveer un componente `PerfilBannerEstado` en `frontend/src/screens/alumno/components/PerfilBannerEstado.tsx` que renderice condicionalmente uno de tres banners según el estado del perfil del alumno, o nada si el perfil está en estado neutro. Los banners son mutuamente excluyentes y tienen esta prioridad: (1) `biometriaCaducada` → banner rojo de error; (2) `biometriaRenovacionRequerida && !biometriaCaducada` → banner amarillo de advertencia; (3) `perfilCompleto && !biometriaCaducada && !biometriaRenovacionRequerida` → banner verde de éxito. Si ninguna condición aplica, el componente no renderiza nada.

Props:
```
perfilCompleto: boolean
biometriaCaducada: boolean
biometriaRenovacionRequerida: boolean
viaAlternativa: boolean
onIrAExamenes: () => void
onRenovarBiometria: () => void
```

#### Scenario: Banner verde cuando perfil completo y sin alertas
- **WHEN** `perfilCompleto=true`, `biometriaCaducada=false`, `biometriaRenovacionRequerida=false`
- **THEN** se muestra un banner con clase `bg-success-container border-success/30` con ícono `verified` y texto "Perfil completo — podés rendir tus exámenes"
- **THEN** el banner incluye un botón "Mis exámenes" que llama `onIrAExamenes`

#### Scenario: Banner verde muestra texto de vía alternativa
- **WHEN** `perfilCompleto=true`, `biometriaCaducada=false`, `biometriaRenovacionRequerida=false`, `viaAlternativa=true`
- **THEN** el subtexto del banner indica "Elegiste la vía alternativa. Un proctor supervisará tu verificación de identidad."

#### Scenario: Banner rojo cuando referencia biométrica caducada
- **WHEN** `biometriaCaducada=true`
- **THEN** se muestra un banner con clase `bg-error-container border-error/30` con ícono `cancel` y texto "Referencia biométrica caducada — no podés rendir"
- **THEN** el banner incluye un `Button variant='danger' size='sm'` que llama `onRenovarBiometria`

#### Scenario: Banner amarillo cuando renovación requerida sin caducar
- **WHEN** `biometriaRenovacionRequerida=true` y `biometriaCaducada=false`
- **THEN** se muestra un banner con clase `bg-warning-container border-warning/30` con ícono `refresh` y texto "Renovación biométrica requerida"
- **THEN** el banner incluye referencia a `<Term termKey="embedding" />` y `<Term termKey="l2_5" />`
- **THEN** el banner incluye un `Button variant='outline' size='sm'` que llama `onRenovarBiometria`

#### Scenario: Sin banner cuando perfil incompleto y sin alertas críticas
- **WHEN** `perfilCompleto=false`, `biometriaCaducada=false`, `biometriaRenovacionRequerida=false`
- **THEN** el componente no renderiza ningún elemento visible
