# Tasks — c-25 Captura de actividad integral

> Reglas duras: el sistema NO sanciona (flaggea + registra para revisión humana). Cliente = sensor no confiable (evidencia re-validada server-side). Componentes React en PascalCase. No buildear ni commitear sin pedido explícito. Tests sin mocks de DB (detectores se testean con dobles de `doc`/`win`, no de base).

## 1. suspicious-activity-catalog

- [ ] 1.1 Declarar el catálogo canónico actividad→tipo→severidad (visión + navegador) como fuente de verdad. **Done**: existe un módulo/const con los 8 tipos (`rostro_ausente`, `multiples_rostros`, `mirada_desviada_sostenida`, `perdida_de_foco`, `cambio_pestana`, `monitor_adicional`, `salida_pantalla_completa`, `copiar_pegar`) y su severidad.
- [ ] 1.2 Agregar los tipos nuevos a `TipoEvento` en `frontend/src/lib/types.ts` (`cambio_pestana`, `salida_pantalla_completa`, `copiar_pegar`). **Done**: `TipoEvento` los incluye y el proyecto typechequea.
- [ ] 1.3 Agregar descripciones y labels en `frontend/src/lib/api.ts` (`DESC_EVENTO`, `TIPO_EVENTO_LABEL`) y sumarlos a `DETECTORES_DEFAULT`. **Done**: cada tipo nuevo tiene descripción y label visibles en UI.
- [ ] 1.4 Verificar compatibilidad con el `event-schema-contract` de C-10 (tipos/severidades del dominio). **Done**: los nuevos tipos son un subconjunto compatible del catálogo de C-10, sin contradecirlo.

## 2. browser-activity-detectors

- [ ] 2.1 Detector de cambio/apertura de pestaña (Page Visibility) distinto de blur de ventana, con dep inyectable `doc`. **Done**: produce señal de cambio de pestaña; test con doble de `doc` cubre hidden→visible.
- [ ] 2.2 `FullscreenDetector` (`fullscreenchange` / `document.fullscreenElement`) con dep inyectable. **Done**: produce señal de salida de fullscreen al pasar de fullscreen a no-fullscreen; test con doble de `doc`.
- [ ] 2.3 `ClipboardDetector` (`copy`/`paste`) que NO lee contenido del portapapeles, con dep inyectable. **Done**: produce señal con la acción (`copy`/`paste`) y sin contenido; test con doble de `doc`.
- [ ] 2.4 Garantizar que ningún detector emite veredicto/sanción (solo señales). **Done**: test/assert de que la salida es señal/evento sospechoso, nunca decisión disciplinaria.

## 3. state-transition-rules (MODIFIED, C-11)

- [ ] 3.1 Extender `FrameSignals` con campos opcionales de navegador (`tab_changed?`, `fullscreen_exited?`, `clipboard_action?`) sin romper firmas existentes. **Done**: el tipo compila y los frames de visión existentes siguen funcionando.
- [ ] 3.2 Emitir `cambio_pestana` (media), `salida_pantalla_completa` (media) y `copiar_pegar` (media) en `evalContext`, con de-dupe para no re-emitir mientras la señal persiste. **Done**: tests deterministas (reloj inyectado) verifican un evento por transición y no re-emisión.
- [ ] 3.3 Confirmar que ninguna transición nueva marca sanción ni deriva veredicto (L2.5). **Done**: test asserta ausencia de cualquier campo/efecto de sanción.

## 4. browser-context-detectors (MODIFIED, C-11) — cablear monitores

- [ ] 4.1 Cablear `detectExtraMonitor` al flujo del alumno en `frontend/src/screens/Examen.tsx`, dejando de hardcodear `extra_monitor: false`. **Done**: cuando hay segundo monitor, el frame lleva `extra_monitor: true`; sin API, degrada a no-determinable sin abortar.
- [ ] 4.2 Cablear todos los detectores de entorno nuevos (pestaña, fullscreen, clipboard) al frame que `Examen.tsx` pasa al pipeline. **Done**: las señales de entorno reales llegan a `stateTransitionRules` en el flujo del alumno.

## 5. admin-detection-test-harness (MODIFIED, C-23)

- [ ] 5.1 Reemplazar en `AdminDetectionHarness.tsx` la inyección fija `focus_lost: false, extra_monitor: false` por las señales de los detectores de contexto reales. **Done**: el loop del harness consume las señales reales de entorno.
- [ ] 5.2 Panel "Señales de entorno" en vivo (foco, pestaña, fullscreen, último copy/paste, estado de monitores). **Done**: el panel refleja en tiempo real el estado de cada detector de navegador.

## 6. integral-activity-validation

- [ ] 6.1 Checklist de cobertura: por cada tipo del catálogo, marcar "capturado y registrado" cuando aparece al menos una vez en el log del harness. **Done**: el checklist se marca al primer evento de cada tipo, con severidad y momento.
- [ ] 6.2 Indicar "no testeable en este navegador" para tipos que dependen de APIs ausentes (monitores múltiples). **Done**: cuando getScreenDetails no está disponible/denegada, el ítem se marca como no testeable sin invalidar el resto.
- [ ] 6.3 Validar aislamiento (D-4): la validación corre sobre el sink local air-gapped, sin emitir al backend ni abrir sesión de alumno. **Done**: ningún evento del harness sale al backend de producción; el aviso L2.5 sigue visible.
- [ ] 6.4 Confirmar cobertura integral completa en una sesión: visión (rostro/mirada/pose/múltiples) + navegador (pestaña/foco/fullscreen/copy-paste/monitores). **Done**: con el operador ejercitando todas las acciones, el checklist alcanza cobertura completa (salvo ítems no testeables).
