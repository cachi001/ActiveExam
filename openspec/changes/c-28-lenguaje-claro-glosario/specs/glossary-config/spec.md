## ADDED Requirements

### Requirement: Módulo central de glosario de términos técnicos
El sistema SHALL proveer un módulo TypeScript en `frontend/src/config/glossary.ts` que exporte un tipo discriminado `TermKey` con las 7 claves canónicas, una interfaz `GlossaryEntry` con campos `label`, `definition` y `legalRef` opcional, y un objeto `GLOSSARY: Record<TermKey, GlossaryEntry>` con las definiciones en lenguaje claro de cada término. El módulo SHALL ser importable directamente por cualquier componente sin hooks ni context providers.

#### Scenario: Import directo del diccionario
- **WHEN** un componente importa `GLOSSARY` desde `../config/glossary`
- **THEN** `GLOSSARY` es un objeto tipado con exactamente las claves `l2_5`, `embedding`, `worm`, `liveness`, `cadena_de_custodia`, `face_mesh`, `datos_biometricos`

#### Scenario: Definición de L2.5 en lenguaje claro
- **WHEN** un componente accede a `GLOSSARY['l2_5'].definition`
- **THEN** la definición explica que el sistema nunca sanciona automáticamente y que la decisión disciplinaria es siempre humana

#### Scenario: Definición de embedding con referencia legal
- **WHEN** un componente accede a `GLOSSARY['embedding']`
- **THEN** `definition` explica que es una representación numérica de la geometría facial tratada como dato sensible, y `legalRef` referencia la Ley 25.326

#### Scenario: Definición de liveness
- **WHEN** un componente accede a `GLOSSARY['liveness'].definition`
- **THEN** la definición explica que es la prueba de que hay una persona viva real frente a la cámara (no foto, video ni máscara)

#### Scenario: Definición de cadena de custodia
- **WHEN** un componente accede a `GLOSSARY['cadena_de_custodia'].definition`
- **THEN** la definición explica que es el registro criptográfico que prueba que la evidencia no fue alterada desde su captura

#### Scenario: Definición de WORM
- **WHEN** un componente accede a `GLOSSARY['worm'].definition`
- **THEN** la definición explica que "Write Once Read Many" significa que el archivo no puede modificarse ni borrarse una vez escrito

#### Scenario: Definición de datos biométricos con referencia legal
- **WHEN** un componente accede a `GLOSSARY['datos_biometricos']`
- **THEN** `definition` explica que son datos derivados de características físicas y `legalRef` referencia la Ley 25.326

#### Scenario: Estructura tipada sin campos extra
- **WHEN** TypeScript compila el módulo `glossary.ts`
- **THEN** no hay errores de tipo; el tipo `TermKey` es un union literal exhaustivo y `GlossaryEntry` tiene exactamente los campos `label: string`, `definition: string`, `legalRef?: string`
