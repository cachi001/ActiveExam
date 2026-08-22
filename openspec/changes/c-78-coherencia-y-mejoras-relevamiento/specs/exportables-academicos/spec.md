# exportables-academicos Specification

## Purpose

Poder sacar del sistema los listados que hoy solo se pueden mirar en pantalla, y reflejar
la realidad de los campus donde no hay API y la nota se carga a mano.

## Requirements

### Requirement: Los inscriptos de una comisión se exportan en PDF y Excel

El sistema SHALL permitir exportar el listado de alumnos inscriptos de una comisión en
PDF y en Excel, con las columnas necesarias para cruzarlo contra Moodle: apellido, nombre,
usuario, email y fecha de inscripción.

#### Scenario: Cruce contra el campus

- **WHEN** un docente exporta los inscriptos de su comisión
- **THEN** obtiene el archivo con los inscriptos actuales y las columnas acordadas

### Requirement: Las notas del examen se exportan

El sistema SHALL permitir exportar las notas del examen con los alumnos que rindieron y
su calificación.

#### Scenario: Campus sin API

- **WHEN** el campus no tiene API disponible y hay que cargar las notas a mano
- **THEN** el docente exporta el listado y lo usa como fuente para la carga manual

### Requirement: El estado de la nota se puede marcar a mano

El sistema SHALL permitir marcar manualmente que la nota de un alumno ya fue cargada en el
campus, sin depender de la sincronización automática.

#### Scenario: Nota cargada a mano

- **WHEN** un docente carga la nota en el campus y la marca como cargada en el sistema
- **THEN** el estado deja de figurar como pendiente

### Requirement: El estado manual se distingue del confirmado y no lo pisa

El sistema SHALL registrar quién marcó el estado a mano y cuándo, SHALL mostrar el origen
del estado en la UI, y MUST NOT permitir que un marcado manual sobrescriba un estado
confirmado por sincronización real.

#### Scenario: Origen visible

- **WHEN** alguien mira el estado de las notas
- **THEN** distingue "confirmado por el campus" de "marcado por {persona} el {fecha}"

#### Scenario: Intento de pisar una confirmación

- **WHEN** se intenta marcar a mano una nota cuyo envío ya fue confirmado por el campus
- **THEN** el sistema rechaza el cambio
