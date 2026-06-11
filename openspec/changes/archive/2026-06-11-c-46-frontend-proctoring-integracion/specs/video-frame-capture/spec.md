## ADDED Requirements

### Requirement: Función pura `captureVideoFrame`
El sistema SHALL proveer una función exportada `captureVideoFrame(videoEl: HTMLVideoElement, quality?: number): string | null` en `frontend/src/lib/videoFrameCapture.ts`. La función SHALL: (a) crear un `HTMLCanvasElement` con las dimensiones del video (`videoWidth`, `videoHeight`), (b) llamar `ctx.drawImage(videoEl, 0, 0)`, (c) retornar `canvas.toDataURL('image/jpeg', quality ?? 0.7)`. Retorna `null` si el elemento de video no tiene un frame válido (`readyState < 2`), si las dimensiones son cero, o si se produce cualquier excepción.

#### Scenario: Captura exitosa del frame actual
- **WHEN** se llama con un `<video>` con `readyState >= 2` y dimensiones no nulas
- **THEN** retorna un string base64 que comienza con `data:image/jpeg;base64,`

#### Scenario: Retorna null si el video no tiene frame
- **WHEN** se llama con un `<video>` con `readyState < 2` o dimensiones cero
- **THEN** retorna `null` sin lanzar excepción

#### Scenario: Calidad JPEG configurable
- **WHEN** se llama con `quality = 0.5`
- **THEN** el canvas.toDataURL se llama con ese valor de calidad; el string resultante es más pequeño que con quality 0.9

#### Scenario: Sin side effects — no modifica el DOM
- **WHEN** se llama múltiples veces consecutivas
- **THEN** cada llamada crea un canvas temporal efímero; no quedan elementos en el DOM

### Requirement: Sin dependencias de React ni de MediaPipe
La función `captureVideoFrame` SHALL ser una función TypeScript pura que no importe ningún módulo de React, ningún módulo de MediaPipe, ni `CameraSnapshotCapture`. Puede importarse desde cualquier contexto (Worker, hook, callback de setInterval).

#### Scenario: Importable desde un callback de setInterval
- **WHEN** se importa y llama desde el frameLoop del harness (un setInterval sin contexto React)
- **THEN** funciona correctamente sin errores de hooks o contexto
