## Context

C-22 reubicó el consentimiento informado y la captura biométrica en el **Perfil**, como un enrollment único, versionado e inmutable, que sirve de **base legal** del tratamiento del dato sensible (Ley 25.326, responsabilidad reforzada). Pero el `design.md` de C-22 dejó explícita una **pregunta abierta**: si la Ley 25.326 / la institución exigen, *además* del acuse de perfil, un acuse **específico por rendición** que reconfirme la finalidad concreta de ese examen.

El usuario resolvió la pregunta con un modelo de **consentimiento EN CAPAS**. Este change C-26 implementa la capa que faltaba (acuse por-examen) y cierra esa pregunta abierta. La demo es frontend (React + Vite + Zustand + Tailwind, mock en `frontend/src/lib/api.ts`), construyendo ENCIMA de C-21 (inscripción, "Mis exámenes", `puedeRendir`) y C-22 (`enrollmentAlumno`, `puedeRendir` con `codigo` semántico). No se sanciona automáticamente (L2.5); el cliente es sensor no confiable.

## Decisions

### 1. Modelo de consentimiento en capas: base de licitud + finalidad específica
Se separan dos actos legales distintos, no redundantes:
- **Capa de perfil (C-22, ya implementada)** — acuse PESADO del dato biométrico/sensible. Texto versionado, acción afirmativa sin casilla premarcada, acuse inmutable, vía alternativa, renovación. Es la **base de licitud** del tratamiento.
- **Capa por-examen (C-26, este change)** — acuse LIVIANO y ESPECÍFICO por instancia de tratamiento. Da **finalidad/propósito concreto** ("esa persona va a rendir ESE examen, bajo ESTE monitoreo, en ESTA fecha") y valor de producto. **NO re-pide la biometría ni el consentimiento pesado: lo REFERENCIA.**

Motivo: la Ley 25.326 exige que el tratamiento tenga una finalidad determinada y específica. Un único acuse genérico de perfil no la satisface por examen concreto; multiplicar el acuse pesado por rendición violaría minimización y fricciona al alumno. El modelo en capas resuelve ambos: una base estable + un acuse liviano específico por examen.

### 2. Fundamento legal — Ley 25.326, finalidad específica
El acuse por-examen instancia el principio de **finalidad** (art. 4, Ley 25.326): el alumno consiente que ESE examen concreto será monitoreado con cámara, pantalla/foco y pestañas, en una fecha y duración determinadas. Importante: el acuse por-examen **NO constituye un nuevo tratamiento del dato biométrico** —no captura ni procesa biometría—; solo **referencia** el acuse de perfil vigente (que sí es la base del tratamiento sensible). Así se evita duplicar el dato sensible (responsabilidad reforzada) mientras se cumple la exigencia de finalidad específica por instancia.

### 3. El acuse por-examen referencia el de perfil, no lo repite
La pantalla de acuse por-examen muestra un resumen del estado de perfil ("Tu consentimiento de perfil está vigente — versión X") y **enlaza** a él, pero no re-presenta el texto pesado ni re-captura biometría. Si el perfil NO está completo (consentimiento de perfil ausente/desactualizado o biometría no vigente), el acuse por-examen **no se ofrece**: primero se deriva a completar el perfil (C-22). El acuse por-examen presupone la base de licitud.

### 4. Acuse inmutable por (estudiante, examen), idempotente
Se registra un `AcuseExamen` por par `(estudiante, examen)` con: `examen_id`, `version` del texto por-examen, `timestamp`, `hash` (simulado en demo) sobre `(estudiante, examen, version, alcance_monitoreo, timestamp)`, y `afirmativo`. Idempotente: si ya existe acuse afirmativo para ese examen, `registrarAcuseExamen` lo retorna sin duplicar (consistente con la idempotencia de `inscribir` en C-21). El hash modela la cadena de custodia (C-12): cliente → backend re-sella server-side; la demo lo mockea pero la spec lo exige como comportamiento.

### 5. Acción afirmativa explícita, sin casilla premarcada
Coherente con RN-CO-02 del consentimiento de perfil: el acuse por-examen exige una acción afirmativa explícita (botón "Confirmo que rendiré este examen bajo monitoreo"), sin casillas premarcadas ni consentimiento por inacción. Si el alumno no confirma, no queda inscripto/habilitado para ese examen, pero no se lo sanciona: se lo deja en el estado previo y puede confirmar más tarde.

### 6. Gate de habilitación en capas conectado a `puedeRendir(examenId)`
El gate de rendir pasa a evaluar DOS condiciones:
1. **Perfil completo** (C-22): consentimiento de perfil vigente (o vía alternativa) + biometría vigente. Resuelto por `recalcularPerfilCompleto(enrollmentAlumno)`.
2. **Acuse por-examen** presente y afirmativo para ESE `examenId`.

`puedeRendir(examenId)` chequea (1) primero (reusando la lógica de C-22 y sus `codigo`: `perfil_incompleto`, `consentimiento_version_desactualizada`, `biometria_caducada`, `biometria_renovacion_requerida`); si (1) pasa pero falta (2), retorna `{ puede: false, codigo: 'acuse_examen_faltante', razon }`. Así el gate es **en capas** sin romper los códigos existentes de C-22: solo agrega un código nuevo. Falta de acuse **deriva** a completarlo (L2.5: flaggea/deriva, nunca sanciona ni veredicta automático).

### 7. Punto de captura: en la inscripción, no en el pre-examen
El acuse por-examen se ofrece en el flujo de **inscripción** (C-21), porque es ahí donde se materializa la decisión de rendir ESE examen. Tras inscribirse + acusar, "Mis exámenes" muestra el examen listo para el gate de rendir. Si por alguna razón el alumno se inscribió sin acusar (p. ej. perfil incompleto en el momento), "Mis exámenes" y el gate `puedeRendir` muestran "Completar acuse del examen" como acción siguiente, derivando al paso de acuse.

## Risks / Trade-offs

- **Doble acuse percibido como fricción**: el alumno consiente dos veces (perfil + examen). Mitigación: el por-examen es LIVIANO (sin re-capturar biometría ni re-leer el texto pesado), referencia el de perfil y se integra al clic de inscripción. El valor legal (finalidad específica) y de producto justifica el paso extra.
- **Acuse por-examen sin perfil completo**: si el perfil no está completo, el acuse por-examen no aplica todavía. Se prioriza derivar a perfil (C-22) primero; el gate ya distingue ambos códigos.
- **Versión del texto por-examen vs. del de perfil**: son versiones independientes. Un cambio en el texto por-examen re-dispara el acuse por-examen del/los examen/es afectados; no toca el acuse de perfil. Las versiones no se mezclan (cada acuse referencia su propia versión).
- **Cliente = sensor no confiable**: el hash del acuse se genera en cliente solo como placeholder de demo; la spec exige que el sellado/firma definitivo sea server-side (cadena de custodia C-12). No editar archivos de C-21/C-22: los cambios viven como deltas dentro de C-26.

## Open Questions

- **Versión y contenido del alcance de monitoreo por examen**: la lista exacta de capacidades monitoreadas a mostrar (cámara, pantalla/foco, pestañas, audio, etc.) puede variar por configuración de examen (C-07). En la demo se modela un alcance representativo; el detalle por configuración queda para integración con `exam-config`.
