## Context

Dos decisiones arquitectónicas ya tomadas dejaron la KB con terminología desactualizada:

**Decisión 1 — C-24 (DD-24-01/03)**: La evidencia de eventos pasó de clip de video (5-10 s) a screenshot (frame único). La KB en 5 archivos sigue usando "clip" para referirse a la evidencia de eventos, contradiciendo DD-24-01/03 y confundiendo a los agentes que leen la documentación.

**Decisión 2 — Modelo biométrico confirmado por el dueño**: El enrollment biométrico opera con **foto de referencia + embedding** (snapshot único), no con clip/video de 3-5 s. `knowledge-base/12_biometria_y_liveness.md` y `knowledge-base/06_funcionalidades.md` aún describen "video corto 3-5s" y "clip de verificación".

## Goals / Non-Goals

**Goals:**
- Alinear la KB con las decisiones ya tomadas: clip→captura (evidencia eventos), clip/video→foto+embedding (biometría).
- Agregar nota DPIA en `10_preguntas_abiertas.md` sobre el tradeoff de liveness temporal server-side.
- Cero cambios de código (.py/.ts).

**Non-Goals:**
- Renombrar variables/símbolos de código (`clip_bytes`, `clipCustody.ts`, `ClipInferencer`): es un refactor separado, fuera de scope.
- Cambiar el modelo de datos ni specs maestros.
- Tocar openspec/specs/ (el proyecto no usa specs archivados).

## Decisions

### D-01: Terminología de evidencia de eventos — "clip" → "captura" o "screenshot"

**Decisión**: Reemplazar todas las referencias a "clip" que refieran a la evidencia de eventos automáticos por "captura" (genérico) o "screenshot"/"captura de pantalla" según el contexto. El término "clip" implica video; la evidencia real es un frame estático.

**Alternativa descartada**: mantener "clip" como término unificado para evidencia — descartado porque contradice explícitamente DD-24-01/03 y confunde a los agentes implementadores.

### D-02: Terminología biométrica — "video/clip" → "foto de referencia (snapshot) + embedding"

**Decisión**: Reemplazar las descripciones de captura biométrica que dicen "video corto 3-5s" o "clip de verificación" por "foto de referencia (snapshot)" y "foto + embedding". El paso de liveness sigue existiendo (está en el paso 2 del flujo biométrico), pero la *captura* que se persiste es una foto, no un clip.

**Detalle del modelo correcto**:
- Enrollment: el usuario saca UN SNAPSHOT (foto) + se guarda foto + embedding de referencia.
- Verificación en examen: se compara el embedding del momento contra el de referencia (1:1).
- El liveness se ejecuta sobre el video live de la cámara en el navegador (sin persistirlo como clip).

**Alternativa descartada**: actualizar el flujo completo del liveness en la KB — fuera de scope; el liveness sigue siendo híbrido (pasivo + retos activos), solo cambia lo que se *persiste*.

### D-03: Nota DPIA obligatoria en 10_preguntas_abiertas.md

**Decisión**: Agregar una nueva sección "Cambios relevantes con impacto de gobernanza" (si no existe) con una nota sobre C-51:

> C-51 consolida el modelo foto+embedding para la biometría de enrollment. Este modelo resuelve **identidad** (1:1 con foto de referencia) pero **NO liveness temporal server-side**: la foto plana no permite re-inferencia temporal (movimiento, parpadeo, profundidad en secuencia). La defensa contra foto-ataque descansa en el liveness que corre en el navegador (cliente no confiable — regla dura #6). El dominio `backend/app/domain/biometrics/liveness.py` existe para la verificación de "rostro real, no foto plana" server-side, pero opera sobre el frame del momento (estático), no sobre una secuencia temporal. El **DPIA (C-01) debe registrar y justificar explícitamente este tradeoff L2.5**.

**Justificación**: la regla dura #6 ("cliente no confiable") y la regla dura #7 (Ley 25.326 + DPIA) exigen que esta tensión quede visible en la documentación de gobernanza. No registrarla sería un defecto.

## Risks / Trade-offs

- **[Aceptado] Liveness temporal server-side fuera de alcance**: foto+embedding resuelve identidad pero no liveness dinámico. La mitigación es el liveness en el navegador (cliente) + verificación continua + revisión humana. Ver nota DPIA (D-03).
- **[Riesgo menor] Inconsistencia residual en código**: `clip_bytes`, `clipCustody.ts`, `ClipInferencer` usan el término antiguo. No es un bug (el código funciona), pero genera deuda de legibilidad. Se resuelve en un refactor de código posterior.
- **[Mitigación] Ningún cambio de comportamiento**: este change no toca lógica, contratos de API ni BD. El riesgo de regresión es cero.

## Migration Plan

1. Editar `knowledge-base/03_actores_y_roles.md`: una referencia clip→captura en la matriz RBAC.
2. Editar `knowledge-base/08_arquitectura_propuesta.md`: una referencia "Descarga de clips" → "Descarga de capturas".
3. Editar `knowledge-base/07_flujos_principales.md`: cuatro referencias en Flujo 4 (clip→captura) + referencias biométricas en Flujo 0 y Flujo 2.
4. Editar `knowledge-base/14_observabilidad_y_devops.md`: "los clips quedan en buffer" → "las capturas quedan en buffer".
5. Editar `knowledge-base/10_preguntas_abiertas.md`: "clips, embeddings, eventos" → "capturas, embeddings, eventos" + agregar sección con nota DPIA.
6. Editar `knowledge-base/12_biometria_y_liveness.md`: "video corto 3-5s" → "foto (snapshot)" en el paso 1; "clip de verificación" → "foto de referencia" en persistencia.
7. Editar `knowledge-base/06_funcionalidades.md`: CA-1 de Épica 4 "video corto 3-5s" → "foto (snapshot)"; CA-6 "El clip y el embedding" → "La foto y el embedding"; Épica 8 US-008 menciones de clip en evidencia.

**Rollback**: revertir los `.md`; sin efectos secundarios (no hay código, no hay migraciones).
