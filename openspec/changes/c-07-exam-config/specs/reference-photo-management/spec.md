# Spec — reference-photo-management

> Carga de la foto institucional de referencia (o marcado como precomputada). Prerrequisito de la verificación 1:1 de C-09 (SU-01). Dato biométrico sensible: cifrado at-rest, finalidad acotada.

## ADDED Requirements

### Requirement: Registro de la foto institucional de referencia
El sistema SHALL permitir al administrador cargar la foto institucional de referencia para un estudiante de un examen, o marcar la referencia como precomputada cuando la institución ya provee el embedding; en ambos casos la referencia queda disponible como prerrequisito de la verificación biométrica 1:1 (SU-01, US-001 CA-4).

#### Scenario: Solicitar URL firmada para subir la foto de referencia
- **WHEN** un administrador envía `POST /api/v1/exams/{id}/reference-photo` para un estudiante
- **THEN** el sistema devuelve una URL firmada para subir el binario directo al storage, sin que el binario transite el backend

#### Scenario: Marcar la referencia como precomputada
- **WHEN** un administrador indica que el embedding de referencia ya está precomputado por la institución
- **THEN** el sistema marca la referencia como precomputada y no exige la carga del binario

#### Scenario: La referencia es prerrequisito de la verificación 1:1
- **WHEN** un examen exige verificación biométrica y un estudiante habilitado no tiene foto de referencia cargada ni marcada como precomputada
- **THEN** el sistema refleja que la referencia falta, de modo que la verificación 1:1 no pueda operar sobre ese estudiante

### Requirement: La foto de referencia es dato biométrico sensible
El sistema SHALL tratar la foto institucional de referencia y su embedding derivado como dato biométrico sensible por defecto: cifrado at-rest, finalidad acotada a la verificación de identidad, sin reutilización para otra finalidad (Ley 25.326, RN-CO-04, RN-BIO-07).

#### Scenario: La referencia se almacena cifrada
- **WHEN** se registra una foto de referencia o su embedding precomputado
- **THEN** el artefacto biométrico se persiste cifrado at-rest y su uso queda restringido a la verificación de identidad del examen
