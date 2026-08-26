# aviso-responsable-faltante Specification

## Purpose

Que "esta materia o esta comisión no tiene a nadie a cargo" se sepa mientras se arma la
estructura, y no cuando el alumno ya rindió.

Encontrado probando producción el 26/8/2026: las tres materias estaban sin profesor y sin
coordinador, y las cinco comisiones sin tutor. Con eso se puede crear una materia, sus
comisiones y sus exámenes, y hacer rendir a los alumnos de punta a punta sin que nada
advierta el hueco. El write-back de notas sale con la credencial del TUTOR de la comisión:
sin tutor responde `sin_docente` y la nota queda retenida. El costo de enterarse tarde no
es un error de pantalla, es un examen rendido cuyas notas no vuelven al campus.

## ADDED Requirements

### Requirement: El resumen del examen informa si su comisión quedó sin tutor

El sistema SHALL informar, en el resumen de un examen, si la comisión asociada no tiene
ningún tutor a cargo.

El dato SHALL distinguir TRES estados: falta tutor, tiene tutor, y no se sabe. "No se
sabe" cubre los listados, que no pagan esa consulta, y los exámenes sin comisión asociada
(D11: la asociación es opcional), donde no hay tutor que buscar.

#### Scenario: La comisión del examen no tiene tutor

- **WHEN** se pide el resumen de un examen cuya comisión no tiene ningún tutor asignado
- **THEN** el resumen indica que falta el tutor

#### Scenario: La comisión del examen tiene tutor

- **WHEN** se pide el resumen de un examen cuya comisión tiene al menos un tutor
- **THEN** el resumen indica que no falta

#### Scenario: El examen no tiene comisión asociada

- **WHEN** se pide el resumen de un examen sin comisión
- **THEN** el resumen no afirma nada sobre el tutor

### Requirement: El listado de materias expone sus responsables

El sistema SHALL devolver, en el listado de materias, tanto los coordinadores como los
profesores asignados a cada una.

Sin los profesores no se puede distinguir "esta materia no tiene a nadie" de "esta materia
no tiene coordinador", que es exactamente la distinción que el aviso necesita hacer.

#### Scenario: Materia con profesor asignado

- **WHEN** se lista el catálogo de materias con un principal que administra la estructura
- **THEN** cada materia incluye sus profesores además de sus coordinadores

#### Scenario: Materia sin ningún responsable

- **WHEN** se lista una materia que no tiene coordinadores ni profesores
- **THEN** ambas listas viajan vacías

### Requirement: El aviso se muestra donde se puede actuar, y calla cuando no aplica

El sistema SHALL mostrar el aviso de responsable faltante en la pantalla donde se arma la
estructura académica y en el detalle del examen.

El sistema MUST NOT mostrar el aviso cuando el responsable está asignado ni cuando el dato
no se consultó. Un cartel que aparece siempre se vuelve parte del decorado y deja de
avisar; y afirmar que falta alguien sin haberlo mirado manda a asignar un responsable que
puede estar ya puesto.

#### Scenario: Detalle de un examen cuya comisión no tiene tutor

- **WHEN** se abre el detalle de ese examen
- **THEN** se avisa que las notas no van a poder devolverse al campus y a quién hay que asignar

#### Scenario: Materia sin profesor ni coordinador en la pantalla de estructura

- **WHEN** se abre la pantalla de materias y comisiones
- **THEN** la materia queda marcada en la lista y el aviso explica qué falta

#### Scenario: Todo asignado

- **WHEN** la materia tiene responsables y la comisión tiene tutor
- **THEN** no se muestra ningún aviso
