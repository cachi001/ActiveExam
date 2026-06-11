## Context

C-38 implementó la captura de DNI (frente + dorso) con `CameraSnapshotCapture` y el flujo secuencial en `EnrollmentDniStep`. Al completar, `api.guardarEscaneDNI(frente, dorso)` retorna un `EscaneDNI` con `captura_completada: true`, pero sin ningún resultado de análisis. La UI muestra solo "DNI registrado (frente y dorso)" — un dead-end informativo que no comunica nada sobre la calidad o coherencia del documento.

**Estado actual del modelo:**
```typescript
// types.ts — C-38
export interface EscaneDNI {
  captura_completada: boolean;
  imagen_frente: string | null;
  imagen_dorso: string | null;
  fecha_captura: string;
}
```

**Restricción arquitectónica clave (RN-GLB-01):** el cliente es un sensor no confiable. La validación REAL (RENAPER, MRZ, autenticidad del chip, PDF417 completo, OCR real) es siempre server-side. Este change produce un análisis MOCK client-side con fines de demostración únicamente, con disclaimer explícito y permanente.

**Restricción L2.5:** el sistema nunca sanciona ni aprueba automáticamente. El análisis indica `'preliminar_ok'` o `'requiere_revision'` — nunca `'aprobado'` ni `'rechazado'`. La decisión final es siempre humana.

**Restricción legal (Ley 25.326):** el DNI es dato sensible. El análisis mock no transmite los datos a ningún tercero (todo permanece en memoria de sesión, en la demo). El disclaimer debe mencionar el tratamiento.

## Goals / Non-Goals

**Goals:**
- Agregar tipo `AnalisisDNI` con checks booleanos, datos OCR mock, score de concordancia y estado preliminar.
- Extender `EscaneDNI` con campo `analisis?` opcional.
- Implementar `api.analizarDNI()` mock con delay realista (1.5–2s) y datos coherentes con el alumno demo.
- Agregar fase "Analizando…" + panel de resultados en `EnrollmentDniStep` tras capturar frente+dorso.
- Mostrar estado del análisis en `StudentProfile` sección DNI.
- Disclaimer permanente en toda vista de resultados del análisis.

**Non-Goals:**
- Análisis real (OCR real, lector PDF417/MRZ real, consulta RENAPER).
- Cambiar el motor de visión (MediaPipe) ni el pipeline de proctoring.
- Guardar el análisis en backend ni en localStorage (solo memoria de sesión, demo).
- Hacer el DNI bloqueante del perfil completo (sigue siendo OPCIONAL).
- Implementar re-inferencia server-side del análisis (eso es C-12 y futuro backend).

## Decisions

### D-1: Tipo `AnalisisDNI` como campo opcional en `EscaneDNI`

Extender `EscaneDNI` con `analisis?: AnalisisDNI` en lugar de un objeto separado. Mantiene la cohesión del dato de escaneo y permite que `StudentProfile` muestre el estado del análisis leyendo `enrollment.dni?.analisis` sin estructuras adicionales.

**Alternativa considerada:** objeto paralelo `AnalisisDNI` con referencia a `escan_id`. Descartado: añade complejidad innecesaria para un mock en demo.

### D-2: Estructura de `AnalisisDNI`

```typescript
export type EstadoAnalisisDNI = 'preliminar_ok' | 'requiere_revision';

export interface AnalisisDNI {
  // Checks de integridad documental
  documento_detectado: boolean;     // imagen no vacía, dimensiones mínimas
  imagen_legible: boolean;          // contraste y nitidez simulados
  tipo_documento: 'dni_argentino';  // siempre 'dni_argentino' en esta demo
  pdf417_leido: boolean;            // código de barras del dorso (mock)

  // Datos OCR mock (coherentes con alumno demo Emiliano Cáceres FRM-23-4912)
  datos_extraidos: {
    numero_documento: string;       // ej. "23.456.789"
    apellido: string;               // "CÁCERES"
    nombre: string;                 // "EMILIANO GASTÓN"
    fecha_nacimiento: string;       // "15/08/1995"
    fecha_vencimiento: string;      // "15/08/2031"
    sexo: 'M' | 'F' | 'X';         // "M"
    cuil: string;                   // "20-23456789-4"
  };

  // Concordancia con referencia biométrica del perfil (C-22)
  concordancia_facial: number;      // 0..1, mock ej. 0.94

  // Estado general (NUNCA 'aprobado' ni 'rechazado' — L2.5)
  estado: EstadoAnalisisDNI;

  // Metadatos del análisis mock
  timestamp_analisis: string;       // ISO 8601
  version_analisis: string;         // "mock-v1"
}
```

**Rationale:** Los campos reflejan lo que un sistema REAL reportaría, pero con valores mock deterministas. Ayuda al demo a ser pedagógicamente honesto sobre qué se verifica.

**Estados permitidos:**
- `'preliminar_ok'`: todos los checks básicos pasan (documento detectado, legible, PDF417 leído, concordancia > 0.85).
- `'requiere_revision'`: algún check falla o concordancia < 0.85 (mock puede variar levemente para realismo).

### D-3: Implementación del mock `api.analizarDNI()`

Función separada de `guardarEscaneDNI` por claridad semántica. `guardarEscaneDNI` devuelve `EscaneDNI` sin análisis (comportamiento existente, compatible). El análisis se dispara explícitamente desde `EnrollmentDniStep` tras el guardado.

**Flujo en `EnrollmentDniStep`:**
1. Captura dorso → `handleDorsoCapturado`
2. Llama `api.guardarEscaneDNI(frente, dorso)` → `EscaneDNI` sin análisis → fase `'completado'`
3. Inmediatamente llama `api.analizarDNI()` → fase `'analizando'` (spinner)
4. Recibe `AnalisisDNI` → fase `'resultado'` (panel)
5. Llama `onEscaneado(escan con analisis adjunto)`

**Mock determinista:**
```typescript
async analizarDNI(): Promise<AnalisisDNI> {
  await delay(1800); // simula procesamiento server-side
  return {
    documento_detectado: true,
    imagen_legible: true,
    tipo_documento: 'dni_argentino',
    pdf417_leido: true,
    datos_extraidos: {
      numero_documento: '23.456.789',
      apellido: 'CÁCERES',
      nombre: 'EMILIANO GASTÓN',
      fecha_nacimiento: '15/08/1995',
      fecha_vencimiento: '15/08/2031',
      sexo: 'M',
      cuil: '20-23456789-4',
    },
    concordancia_facial: 0.94,
    estado: 'preliminar_ok',
    timestamp_analisis: new Date().toISOString(),
    version_analisis: 'mock-v1',
  };
}
```

**Alternativa considerada:** integrar el análisis dentro de `guardarEscaneDNI`. Descartado: combina dos responsabilidades y dificulta la evolución futura donde el análisis real será un endpoint separado del servidor.

### D-4: Fases del flujo en `EnrollmentDniStep`

```typescript
type Fase = 'inicio' | 'analizando' | 'resultado' | 'completado';
```

- `'inicio'`: UI actual con botones de captura.
- `'analizando'`: spinner "Verificando documento…" durante el delay del mock (~1.8s).
- `'resultado'`: panel de resultados completo con checks, datos, concordancia y disclaimer.
- `'completado'`: estado existente, ahora solo usado para re-entrar si ya tenía análisis previo.

### D-5: Panel de resultados — UX

El panel se construye con componentes existentes (`Card`, `Badge`, `Icon`) sin nuevas dependencias de UI.

**Secciones del panel:**
1. **Checks de integridad** (fila de chips): Documento detectado ✓ / Imagen legible ✓ / Tipo: DNI Argentino / Código de barras ✓.
2. **Datos extraídos** (grid): Nombre, Apellido, N° Documento, Fecha de nacimiento, Vencimiento, CUIL — con nota "Extraídos por OCR (demo)".
3. **Concordancia facial** (barra de progreso con color): X% de similitud con la referencia biométrica del perfil — con explicación breve.
4. **Estado general** (badge prominente): "Análisis preliminar — OK" o "Análisis preliminar — Requiere revisión".
5. **Disclaimer obligatorio** (card con icono `info`):

> "Análisis indicativo (demo). La validación oficial del documento (RENAPER, autenticidad, MRZ/PDF417) se realiza server-side. El cliente es un sensor no confiable (RN-GLB-01). Este resultado es preliminar y está sujeto a revisión humana — el sistema no aprueba ni rechaza automáticamente (L2.5)."

### D-6: Resumen en `StudentProfile` sección DNI

Cuando `enrollment.dni?.analisis` existe, la sección DNI muestra:
- Badge: "Análisis preliminar OK" (tone: success) o "Análisis — Requiere revisión" (tone: warning).
- Texto secundario: "Fecha de análisis: {timestamp_analisis}" + nota sobre revisión humana.

Mantiene el botón "Escanear DNI (opcional)" cuando no hay análisis aún, y el texto existente cuando `ENABLE_DNI_SCAN` es false.

## Risks / Trade-offs

- **[Riesgo] Mock determinista puede confundir usuarios de prueba** → Mitigación: disclaimer en todas las vistas, badge "DEMO / mock-v1" en los datos extraídos, y la `version_analisis: 'mock-v1'` visible en el panel técnico.

- **[Riesgo] Concordancia facial mock (0.94) fijo puede parecer "siempre perfecta"** → Mitigación: agregar variabilidad leve basada en timestamp (ej. `0.90 + Math.sin(Date.now() / 1e7) * 0.06`) para que no sea siempre idéntica, pero sin ser confusamente mala.

- **[Trade-off] `analizarDNI` separado de `guardarEscaneDNI`** → Un endpoint más en la api mock, pero mejor separación de responsabilidades y más fiel a la arquitectura real (guardado ≠ análisis).

- **[Riesgo] Datos OCR mock exponen datos personales ficticios** → Los datos son ficticios y coherentes con el perfil demo; no son datos reales de ninguna persona. El disclaimer lo aclara.

## Open Questions

- ¿Debe el análisis variar (levemente) entre corridas para mayor realismo, o mantenerse estrictamente determinista para tests automáticos? **Decisión adoptada**: base determinista con variación cosmética en `concordancia_facial` (dentro de rango 0.88–0.96) para realismo sin afectar el estado (`'preliminar_ok'`).
