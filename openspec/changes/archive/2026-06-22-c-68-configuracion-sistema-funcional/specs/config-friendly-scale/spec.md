# config-friendly-scale

## ADDED Requirements

### Requirement: Representación de configuración en "números más fáciles"
La UI de admin SHALL presentar los parámetros de configuración en una escala intuitiva para el usuario no técnico, mapeando las unidades internas a representaciones amigables: los tiempos en milisegundos (`face_absent_ms`, `gaze_sustained_ms`) SHALL mostrarse en **segundos**; los umbrales normalizados 0–1 (`gaze_deviation_threshold`, `gaze_fixation_tolerance`) SHALL mostrarse como **sensibilidad** (baja/media/alta); los conteos de fotogramas (`multiple_faces_frames`) SHALL mostrarse como "N detecciones seguidas". Los valores autoritativos SHALL permanecer en unidades internas server-side.

#### Scenario: Tiempo en ms se muestra en segundos
- **WHEN** la UI muestra `face_absent_ms = 3000`
- **THEN** SHALL presentarlo como "3 segundos"

#### Scenario: Umbral 0–1 se muestra como sensibilidad
- **WHEN** la UI muestra `gaze_deviation_threshold = 0.20`
- **THEN** SHALL presentarlo en una escala de sensibilidad amigable (baja/media/alta), no como "0.20"

### Requirement: Conversión bidireccional sin pérdida de autoridad
La capa de presentación SHALL convertir la escala amigable a la unidad interna antes de enviar cualquier edición al backend; el cliente SHALL NO enviar la escala amigable cruda. La conversión SHALL implementarse en un módulo TypeScript puro de `frontend/src/config/` (patrón `institution-config`), con tests.

#### Scenario: La edición se persiste en unidad interna
- **WHEN** un `admin_sistema` edita "3 segundos" en la UI y guarda
- **THEN** el cliente SHALL enviar `face_absent_ms = 3000` al backend (no "3")

#### Scenario: Round-trip preserva el valor
- **WHEN** un valor interno se convierte a la escala amigable y de vuelta a interno
- **THEN** el valor interno resultante SHALL ser igual al original (dentro de la granularidad de la escala)
