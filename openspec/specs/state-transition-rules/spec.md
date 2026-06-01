# Spec delta — state-transition-rules (C-11)

> Extiende las reglas de transición para emitir eventos discretos de los nuevos tipos de actividad de navegador, manteniendo la garantía de no-sanción (L2.5).

## MODIFIED Requirements

### Requirement: Transiciones de contexto de navegador
Las reglas de transición SHALL convertir las señales de contexto de navegador en eventos discretos con severidad: pérdida de foco de ventana → `perdida_de_foco` (baja), monitor adicional → `monitor_adicional` (alta), cambio o apertura de pestaña → `cambio_pestana` (media), salida de pantalla completa → `salida_pantalla_completa` (media) y actividad de copiar/pegar → `copiar_pegar` (media). Los eventos de navegador son discretos e instantáneos: se emiten en el frame en que la señal está presente y SHALL aplicar de-duplicación básica para no re-emitir el mismo estado de forma repetida mientras la señal persiste. NINGUNA transición SHALL derivar una sanción automática.

#### Scenario: Pérdida de foco de ventana
- **WHEN** la señal `focus_lost` está presente en el frame
- **THEN** las reglas emiten un evento `perdida_de_foco` de severidad baja, sin sanción

#### Scenario: Cambio o apertura de pestaña
- **WHEN** la señal de cambio de pestaña está presente en el frame
- **THEN** las reglas emiten un evento `cambio_pestana` de severidad media, distinto de `perdida_de_foco`, sin sanción

#### Scenario: Salida de pantalla completa
- **WHEN** la señal de salida de pantalla completa está presente en el frame
- **THEN** las reglas emiten un evento `salida_pantalla_completa` de severidad media, y no lo re-emiten hasta que el examen vuelva a entrar y salir de pantalla completa

#### Scenario: Copiar o pegar
- **WHEN** la señal de actividad de portapapeles (copy/paste) está presente en el frame
- **THEN** las reglas emiten un evento `copiar_pegar` de severidad media, sin capturar el contenido del portapapeles y sin sanción

#### Scenario: Monitor adicional
- **WHEN** la señal `extra_monitor` está presente en el frame
- **THEN** las reglas emiten un evento `monitor_adicional` de severidad alta, sin sanción
