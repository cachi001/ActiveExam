# Biometría y Liveness

Complementa `05_reglas_de_negocio.md` (RN-BIO) y `09_decisiones_y_supuestos.md` (DD-18).

## Flujo de verificación en cuatro pasos

1. **Captura**: video corto (3–5 s) con instrucciones claras.
2. **Liveness**: confirma que hay una persona viva, no una foto/video/máscara. Señales: parpadeo natural involuntario, micro-movimientos faciales, profundidad estimada por la geometría 3D de los 468 landmarks de Face Mesh.
3. **Embedding**: vector numérico (típicamente 128–512 dimensiones) que representa rasgos distintivos del rostro.
4. **Comparación 1:1**: distancia coseno contra el embedding precomputado de la foto institucional; si < umbral, verificación exitosa.

## Umbrales, reintentos y verificación continua

- Umbral configurado **conservadoramente**: rechazar a un legítimo es peor que aceptar a un impostor en este paso (el impostor aún debe superar la verificación continua).
- Hasta 2 reintentos; al 3.º fallo se genera evento crítico que escala a proctor.
- **Verificación silenciosa continua**: durante todo el examen compara el embedding del rostro detectado en cada inferencia contra el inicial; una desviación significativa dispara evento crítico de "posible cambio de identidad".

## Persistencia y privacidad

- Se persisten dos artefactos: el clip de verificación (misma cadena de custodia que cualquier evidencia) y el embedding (cifrado at-rest, para la verificación continua).
- El embedding es un vector de números, no la foto ("huella matemática"); se elimina al egreso del estudiante.

### Riesgos biométricos y mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Liveness bypaseable con video pregrabado de calidad | Aceptado como límite del paradigma cliente; combinado con verificación continua + revisión humana |
| Estudiantes sin foto institucional limpia | Proceso de registro previo gestionado por la institución (prerrequisito) |
| Falsos negativos (rechazo de legítimos) | Umbrales conservadores, 2 reintentos, escalación a proctor |
| Embeddings como datos personales protegidos | Cifrado at-rest, retención específica, eliminación al egreso, consentimiento + derechos del titular |

## Liveness: enfoques y estándar

| Enfoque | Cómo funciona | Ventajas | Desventajas |
|---------|---------------|----------|-------------|
| Pasivo | Analiza imagen/video corto buscando artefactos de spoofing (moiré, bordes de papel, falta de profundidad) sin pedir acción | Sin fricción, rápido, difícil de ensayar | Vulnerable a deepfakes de alta fidelidad e inyección |
| Activo | Pide una acción (parpadear, girar la cabeza, seguir un punto) y verifica que ocurra | Confirma interacción en tiempo real | Más fricción; un deepfake "puppet master" puede ejecutar la acción |
| **Híbrido (recomendado)** | Combina análisis pasivo continuo con 1–2 retos activos aleatorios | Sube el costo del ataque; equilibra seguridad y experiencia | Algo más de complejidad |

### Estándar de evaluación: ISO/IEC 30107-3 (PAD)
- **APCER** (Attack Presentation Classification Error Rate): proporción de ataques clasificados como legítimos (menor es mejor).
- **BPCER** (Bona Fide Presentation Classification Error Rate): proporción de personas reales rechazadas (equivale al falso rechazo).
- Niveles de certificación: Nivel 1 (fotos/videos de reproducción), Nivel 2 (máscaras de mediana sofisticación — umbral comercial razonable), Nivel 3 (máscaras de silicona hiperrealistas).

## Amenaza moderna: deepfakes e inyección de cámara (2024–2026)

La amenaza ya no es solo el ataque de presentación (mostrar algo a la cámara) sino la **inyección de cámara** (camera pipe injection): el atacante evita la cámara física e inyecta video sintético (deepfake en tiempo real) directamente en el flujo de la app. Un deepfake "puppet master" puede ejecutar los retos activos en vivo.

**Implicación honesta**: ningún liveness que corra en el navegador puede garantizar inmunidad a la inyección (el cliente es manipulable por definición). La defensa realista combina: liveness + detección de cámara virtual + re-inferencia server-side + verificación continua + revisión humana.

## Recomendación escalonada (DD-18)

- **MVP (Fase 1)**: liveness híbrido propio (pasivo + 1–2 retos activos aleatorios) en el navegador, reforzado con re-inferencia server-side y detección de cámara virtual.
- **Fase 2**: modelo pasivo open-source self-hosted (tipo Silent-Face-Anti-Spoofing, DeePixBiS u otros con licencia compatible) ejecutado server-side sobre el clip.
- **Fase 3**: SDK comercial certificado PAD Nivel 2+ **solo si** la institución eleva el nivel de impacto (dispara revisión del Acuerdo de Nivel de Proctoring).

En todos los casos: el liveness eleva el costo del fraude de identidad, pero la **verificación continua y la revisión humana siguen siendo la red de seguridad**.
