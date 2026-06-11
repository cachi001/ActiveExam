## Why

La knowledge-base usa el término **"clip"** en dos contextos que quedaron desactualizados tras las decisiones C-24 (DD-24-01/03) y la definición del modelo biométrico del dueño del producto:

1. **Evidencia de eventos**: desde C-24 la evidencia automática es un **screenshot** (frame único, ~KB), no un clip de video (5-10 s, ~MB). Sin embargo varios archivos de la KB siguen usando "clip" para referirse a esa evidencia, lo que contradice la decisión tomada y genera confusión documental.

2. **Verificación biométrica**: el dueño definió explícitamente que el modelo de enrollment es **foto de referencia + embedding** (snapshot único), no un clip/video de 3-5 s. La KB todavía describe "captura video 3-5s" y "se persisten el clip de verificación y el embedding", lo que contradice el modelo real implementado.

**¿Por qué ahora?** C-50 (proctor alcance global) se archivó. La KB tiene inconsistencias documentadas que confunden a los agentes (leen "clip" y asumen video, chocando contra el código que opera con screenshots/fotos). Este change es **docs-only sobre la KB**; no toca código (.py/.ts).

## What Changes

- **Evidencia de eventos** (`07`, `03`, `08`, `14`, `10`): reemplaza las referencias a "clip" (que implican video) por "captura" o "screenshot" — alineando con DD-24-01/03.
- **Biometría** (`12`, `06`, `07`): reemplaza "video corto 3-5s" y "clip de verificación" por "foto de referencia (snapshot)" y "foto + embedding" — alineando con el modelo real de enrollment.
- **Nota DPIA obligatoria** (`10`): agrega en `10_preguntas_abiertas.md` una nota explícita sobre que el modelo foto+embedding (C-51) **no resuelve liveness temporal server-side** — el DPIA (C-01) debe registrar/justificar ese tradeoff L2.5. Referencia `backend/app/domain/biometrics/liveness.py`.

## Capabilities

### Modified Capabilities

- `knowledge-base-documentation`: corrección de terminología en 6 archivos de `knowledge-base/`. No hay nuevas capabilities; no hay cambio de comportamiento de sistema.

## Impact

- **Solo knowledge-base/**: 6 archivos `.md` modificados. Cero archivos de código (.py/.ts) tocados.
- **Sin impacto en**: contratos de API, BD, lógica de negocio, tests, frontend, backend.
- **Alineación con decisiones formales**: DD-24-01 (screenshot reemplaza clip), DD-18/RN-BIO (modelo enrollment foto+embedding), regla dura #6 (cliente no confiable → nota DPIA).
- **Archivos afectados**:
  - `knowledge-base/03_actores_y_roles.md` — "clip vía URL firmada 15 min" → "captura vía URL firmada 15 min"
  - `knowledge-base/07_flujos_principales.md` — "PUT clip" / "GET clip" / ":122 el clip queda en buffer" / ":177 clips firmados" / biometría "captura video 3-5s" → captura/screenshot/foto
  - `knowledge-base/08_arquitectura_propuesta.md` — "Descarga de clips vía URL firmada" → "Descarga de capturas vía URL firmada"
  - `knowledge-base/10_preguntas_abiertas.md` — "clips, embeddings, eventos" → "capturas, embeddings, eventos" + nueva sección con nota DPIA
  - `knowledge-base/12_biometria_y_liveness.md` — "video corto 3-5s" / "clip de verificación" → "foto de referencia (snapshot)" / "foto + embedding"
  - `knowledge-base/06_funcionalidades.md` — CA-6 "El clip y el embedding se persisten" → "La foto y el embedding se persisten"; CA-1 en biometría "video corto 3-5s" → "foto (snapshot)"
